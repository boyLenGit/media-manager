"""文件名解析器抽象基类 + 数据类型。

设计:
- 解析是一条"流水线",多个 parser 按优先级串联
- 每个 parser 都接收 ParsedName 作为输入,返回新的 ParsedName(链式修改)
- DefaultParser 永远在最后兜底,负责最基础的清洗
- 特化 parser (Bilibili/Anime/...) 在前置阶段把"特殊后缀"先剥掉

使用流程:
    raw_name = "我们其实是未出道的女团W&M2 - 1.我们其实是女团(Av10285316,P1)"

    pipeline = ParserPipeline.from_config(["bilibili", "anime", "default"])
    result = pipeline.parse(raw_name)

    # → result.title = "我们其实是未出道的女团W&M2"
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from typing import ClassVar


@dataclass
class ParsedName:
    """解析中间产物,可以被多个 parser 链式处理。

    - raw: 原始输入(整条 pipeline 不变)
    - working: 当前正在处理的字符串,每个 parser 修改它
    - title: 最终干净的标题(由最后的 default parser 写入)
    - normalized_title: 用于去重比对(小写、去空格)
    - applied: 记录已经跑过的 parser 名称,便于调试
    """

    raw: str
    working: str
    title: str = ""
    normalized_title: str = ""
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    quality: str | None = None
    release_group: str | None = None
    language_tags: list[str] = field(default_factory=list)
    applied: list[str] = field(default_factory=list)

    def with_working(self, new_working: str) -> "ParsedName":
        return replace(self, working=new_working)


class FilenameParser(ABC):
    """解析器基类。

    实现要求:
    - parse() 接收上一步产物,返回新的产物
    - 不应改 raw,只能改 working / 字段
    - 每次调用都应是幂等的(再调一次结果不变)
    """

    name: ClassVar[str] = "base"
    description: ClassVar[str] = ""

    @abstractmethod
    def parse(self, p: ParsedName) -> ParsedName:
        """子类实现具体清洗逻辑。"""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
