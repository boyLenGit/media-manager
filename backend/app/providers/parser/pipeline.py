"""解析器流水线 + 注册中心。

注册新 parser:
1. 在 providers/parser/ 下新建一个文件,继承 FilenameParser
2. 在 PARSERS 字典里加一项 (key 是 parser.name)
3. 默认配置 DEFAULT_PIPELINE 决定开箱即用启用哪些

用户可以在「设置 → 解析器」里调整启用哪些和顺序。
"""
from __future__ import annotations

import logging

from app.providers.parser.anime_parser import AnimeParser
from app.providers.parser.base import FilenameParser, ParsedName
from app.providers.parser.bilibili_parser import BilibiliParser
from app.providers.parser.default_parser import DefaultParser
from app.providers.parser.jpav_parser import JPAVParser

logger = logging.getLogger(__name__)


# 所有可用的 parser 注册在这里(key = parser.name)
PARSERS: dict[str, type[FilenameParser]] = {
    "bilibili": BilibiliParser,
    "anime": AnimeParser,
    "jpav": JPAVParser,
    "default": DefaultParser,
}

# 默认的 pipeline:特化 parser 在前,default 兜底。
# jpav 放在 default 之前 —— 它只做"FC2-PPV 各种写法归一化",归一化后再交给
# default 做通用清洗(剥分辨率/语言标记等),顺序反了就失去归一化的意义。
DEFAULT_PIPELINE = ["bilibili", "anime", "jpav", "default"]


def list_available() -> list[dict]:
    """供前端展示的列表。"""
    return [
        {
            "name": cls.name,
            "description": cls.description,
            "is_default": cls.name == "default",
        }
        for cls in PARSERS.values()
    ]


class ParserPipeline:
    """串联多个 parser 处理文件名。"""

    def __init__(self, parsers: list[FilenameParser]):
        self.parsers = parsers

    def parse(self, filename_no_ext: str) -> ParsedName:
        """从文件名(已去扩展名)开始,跑完整 pipeline。

        如果传入的是带扩展名文件名,会自动去掉扩展名(只去最后一个 .xxx,
        不能用 Path.stem 因为它对中文带 . 的文件名会判断错)。
        """
        # 自动去最后一段扩展名:.mp4 / .mkv 等只有 2-5 字符且没空格的
        stem = filename_no_ext
        idx = stem.rfind(".")
        if 0 < idx < len(stem) - 1:
            ext = stem[idx + 1 :]
            if 1 <= len(ext) <= 5 and ext.replace("_", "").isalnum() and " " not in ext:
                stem = stem[:idx]

        result = ParsedName(raw=stem, working=stem)
        for parser in self.parsers:
            try:
                result = parser.parse(result)
            except Exception as e:  # noqa: BLE001
                logger.warning("parser %s failed: %s", parser.name, e)
        return result

    @classmethod
    def from_config(cls, names: list[str] | None = None) -> "ParserPipeline":
        """根据 parser 名称列表构造 pipeline。

        - 未知的 name 会被跳过并打 warning
        - 如果列表里没有 default,会自动追加在末尾(保证总是有兜底)
        """
        if not names:
            names = list(DEFAULT_PIPELINE)
        else:
            names = list(names)

        parsers: list[FilenameParser] = []
        seen: set[str] = set()
        for n in names:
            if n in seen:
                continue
            cls_ = PARSERS.get(n)
            if cls_ is None:
                logger.warning("unknown parser: %s, skipped", n)
                continue
            parsers.append(cls_())
            seen.add(n)

        # 兜底:总要有 default
        if "default" not in seen:
            parsers.append(DefaultParser())

        return cls(parsers)
