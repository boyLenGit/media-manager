"""动漫文件名解析器。

动漫资源典型命名:
- [VCB-Studio] Steins;Gate [01][Ma10p_1080p][x265_2flac]
- [Nekomoe kissaten][Hibike! Euphonium 2][13][BDRip][1080P][HEVC_10bit_FLAC]
- [桜都字幕组][SPYxFAMILY][03v2][1080p AVC AAC][CHS_JPN].mp4
- 鬼灭之刃 第01集 [1080p].mkv

特征:
- 发布组在最前面用 [组名] 包起来 (一个或多个)
- 标题在中间,可能含中英双语
- 末尾通常有 [集数][分辨率][编码] 等多个方括号
- 集数可能用 [01]、[01v2]、第01集、E01 等多种形式

策略:
- 第一个方括号 (如果在串首) 视作发布组
- 中间方括号里如果是纯 数字/数字v数字 当作集数,提取后移除整个方括号
- 不处理标题前面没方括号的常规情况(交给 default)

为什么不直接删所有方括号?
- 因为「[Hibike! Euphonium 2]」这种括号里就是标题本身
- 所以我只删能识别为元数据的方括号,文本类的方括号留给 default
"""
from __future__ import annotations

import re

from app.providers.parser.base import FilenameParser, ParsedName


# 第 1 个方括号 (在串首) 视作发布组
_LEADING_GROUP = re.compile(r"^\s*\[([^\]]+)\]\s*")

# "标题方括号":第二个方括号一般是真标题(如 [Hibike! Euphonium 2]),
# 仅当其内容包含字母/汉字时才认为是标题(纯数字/编码标记不是)
_LIKELY_TITLE_BRACKET = re.compile(r"^\s*\[([^\]]+)\]\s*")

# 集数方括号:[01] [01v2] [11.5]
_BRACKET_EPISODE = re.compile(r"\[(\d{1,3})(?:v\d+|\.\d+)?\]")

# 元数据方括号(全是大小写英文/数字/_/分辨率/编码,没汉字),整个删掉
_META_BRACKET = re.compile(
    r"\[(?=[^\]]*[A-Za-z0-9])[A-Za-z0-9_\-\.\s]+\]"
)

# 中文集数 "第01集" "第 1 集"
_CN_EPISODE = re.compile(r"第\s*(\d{1,3})\s*[集话]")


class AnimeParser(FilenameParser):
    name = "anime"
    description = "动漫特化:[发布组] 前缀、集数、Ma10p 等编码标记"

    def parse(self, p: ParsedName) -> ParsedName:
        work = p.working
        release_group = p.release_group
        episode = p.episode

        # 1. 提取首个 [发布组]
        if release_group is None:
            m = _LEADING_GROUP.match(work)
            if m:
                # 启发式:发布组通常含字母 + 不含逗号问号等普通文字
                content = m.group(1).strip()
                if re.match(r"^[A-Za-z0-9_\-\.\s\u4e00-\u9fff]+$", content):
                    release_group = content
                    work = _LEADING_GROUP.sub("", work, count=1)

        # 2. 如果剥完发布组后头部还有一个方括号,且内容像"标题"
        #    (有字母/汉字 + 长度 > 2),把它替换为内容(去掉方括号)
        #    例如 "[Hibike! Euphonium 2][13]" → "Hibike! Euphonium 2 [13]"
        m = _LIKELY_TITLE_BRACKET.match(work)
        if m:
            content = m.group(1).strip()
            # 不是纯数字(那是集数,前面应该已经被处理)
            if len(content) > 2 and not content.isdigit() and re.search(r"[A-Za-z\u4e00-\u9fff]", content):
                work = _LIKELY_TITLE_BRACKET.sub(content + " ", work, count=1)

        # 3. 提取集数(优先方括号)
        if episode is None:
            m = _BRACKET_EPISODE.search(work)
            if m:
                try:
                    episode = int(m.group(1))
                    work = _BRACKET_EPISODE.sub("", work, count=1)
                except ValueError:
                    pass
            if episode is None:
                m = _CN_EPISODE.search(work)
                if m:
                    try:
                        episode = int(m.group(1))
                    except ValueError:
                        pass

        # 4. 删除元数据方括号(BDRip / 1080P / HEVC_10bit_FLAC 这种)
        work = _META_BRACKET.sub(" ", work)
        work = re.sub(r"\s+", " ", work).strip()

        return ParsedName(
            raw=p.raw,
            working=work,
            title=p.title,
            normalized_title=p.normalized_title,
            year=p.year,
            season=p.season,
            episode=episode,
            quality=p.quality,
            release_group=release_group,
            language_tags=p.language_tags,
            applied=p.applied + [self.name],
        )
