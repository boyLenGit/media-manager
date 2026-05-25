"""默认解析器 — 通用清洗规则。

它是 pipeline 的"最后一棒",负责:
- 剥离常见的分辨率/编码/来源/语言等噪声标记
- 提取年份、季集
- 处理发布组(release group)
- 生成最终的 title 和 normalized_title

修复:
- 之前用 \\b 边界,中文环境下不可靠;改成"宽松边界"(允许字母/数字/汉字相邻)
- 「4khevc」这种连贴现在能被正确切开
- 增强中文标记(中英双语 / 内嵌 / 中字 / 双语字幕 等)
"""
from __future__ import annotations

import re

from app.providers.parser.base import FilenameParser, ParsedName

# ============================================================
# 噪声标记 (按出现频率排序)
# ============================================================
# 边界规则:
# - 前面要么是开头/分隔符 (空格 . _ - 等)
# - 后面要么是结尾/分隔符
# 这样能匹配 "1080p" "x265" "4khevc" 等紧贴的情况
_BOUNDARY = r"(?:^|(?<=[\s._\-\[\]\(\)\{\}]))"
_BOUNDARY_END = r"(?=$|[\s._\-\[\]\(\)\{\}]|[a-zA-Z]|[\u4e00-\u9fff])"


def _make_word(*alternatives: str) -> str:
    """构造一个词级匹配(前后宽松边界)。"""
    return _BOUNDARY + r"(?:" + "|".join(alternatives) + r")" + _BOUNDARY_END


# 分辨率
RESOLUTION_PATTERNS = [
    r"(?:480|540|576|720|1080|1440|2160|4320)[pi]",
    r"4[Kk]",
    r"8[Kk]",
    r"UHD",
    r"FHD",
    r"\bHD\b",
    r"\bSD\b",
]

# 编码
CODEC_PATTERNS = [
    r"[Hh]\.?264",
    r"[Hh]\.?265",
    r"[xX]264",
    r"[xX]265",
    r"HEVC",
    r"AVC",
    r"AV1",
    r"VP9",
    r"AAC",
    r"AC3",
    r"DTS(?:-HD)?",
    r"FLAC",
    r"MP3",
    r"10[Bb]it",
    r"8[Bb]it",
    r"Atmos",
    r"DDP?5\.1",
    r"TrueHD",
]

SOURCE_PATTERNS = [
    r"BluRay",
    r"BDRip",
    r"BRRip",
    r"WEB-?DL",
    r"WEBRip",
    r"HDTV",
    r"DVDRip",
    r"Remux",
    r"REMUX",
    r"HDR(?:10\+?)?",
    r"DV",  # Dolby Vision
    r"EXTENDED",
    r"PROPER",
    r"REPACK",
    r"DC",  # Director's Cut
]

LANG_PATTERNS = [
    r"CHS",
    r"CHT",
    r"JPN",
    r"ENG",
    r"KOR",
    r"GB",
    r"BIG5",
    r"简(?:体)?(?:中文)?",
    r"繁(?:体)?(?:中文)?",
    r"国(?:语|配)",
    r"粤(?:语)?",
    r"英(?:语|文)",
    r"日(?:语|文)",
    r"中英(?:双语)?",
    r"中日(?:双语)?",
    r"中(?:文)?字幕",
    r"内嵌(?:字幕)?",
    r"外挂(?:字幕)?",
    r"双语(?:字幕)?",
    r"中字",
    r"原盘",
]

YEAR_PATTERN = re.compile(r"(?<![0-9])(19\d{2}|20\d{2})(?![0-9])")
SEASON_EPISODE_PATTERN = re.compile(r"\b[Ss](\d{1,2})[Ee](\d{1,3})\b")
RELEASE_GROUP_PATTERN = re.compile(r"-([A-Za-z0-9]{2,12})$")


def _strip_brackets(s: str) -> str:
    """剥离 [...] (...) {...}  内嵌的杂讯,只保留主题文本。"""
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = re.sub(r"\([^\)]*\)", " ", s)
    s = re.sub(r"\{[^\}]*\}", " ", s)
    return s


def _extract_quality(s: str) -> str | None:
    for pat in RESOLUTION_PATTERNS:
        m = re.search(_BOUNDARY + r"(" + pat + r")" + _BOUNDARY_END, s)
        if m:
            return m.group(1)
    return None


def _strip_pattern_list(s: str, patterns: list[str]) -> tuple[str, list[str]]:
    """剥离一组模式,返回 (清理后字符串, 命中的标记列表)。"""
    found: list[str] = []
    for pat in patterns:
        regex = re.compile(_BOUNDARY + r"(" + pat + r")" + _BOUNDARY_END, re.IGNORECASE)
        for m in regex.finditer(s):
            found.append(m.group(1))
        s = regex.sub(" ", s)
    return s, found


class DefaultParser(FilenameParser):
    name = "default"
    description = "通用规则:剥离分辨率/编码/语言标记,提取年份和季集"

    def parse(self, p: ParsedName) -> ParsedName:
        work = p.working

        # 提取年份
        year = p.year
        if year is None:
            m = YEAR_PATTERN.search(work)
            if m:
                year = int(m.group(1))

        # 提取季集
        season = p.season
        episode = p.episode
        m = SEASON_EPISODE_PATTERN.search(work)
        if m:
            season = season or int(m.group(1))
            episode = episode or int(m.group(2))

        # 提取分辨率
        quality = p.quality or _extract_quality(work)

        # 剥离方括号
        work = _strip_brackets(work)

        # 在汉字与英文/数字交界处插入空格,辅助后续边界匹配
        # "名称4khevc" → "名称 4khevc",这样 4k 就能被正常匹配
        work = re.sub(r"(?<=[\u4e00-\u9fff])(?=[A-Za-z0-9])", " ", work)
        work = re.sub(r"(?<=[A-Za-z0-9])(?=[\u4e00-\u9fff])", " ", work)

        # 反复剥离直到稳定(因为剥完一个标记可能产生新的边界)
        lang_tags: list[str] = []
        for _ in range(3):
            before = work
            work, _ = _strip_pattern_list(work, RESOLUTION_PATTERNS)
            work, _ = _strip_pattern_list(work, CODEC_PATTERNS)
            work, _ = _strip_pattern_list(work, SOURCE_PATTERNS)
            work, langs = _strip_pattern_list(work, LANG_PATTERNS)
            lang_tags.extend(langs)
            if work == before:
                break

        # 剥离年份和季集
        work = YEAR_PATTERN.sub(" ", work)
        work = SEASON_EPISODE_PATTERN.sub(" ", work)

        # 剥离尾部 release group(只在没被特化 parser 处理过时才剥)
        # 反复剥,有时一次只能剥一段(如 "-VCB-Studio" 会先剥 Studio 再剥 VCB)
        release_group = p.release_group
        for _ in range(3):
            rg = RELEASE_GROUP_PATTERN.search(work)
            if not rg:
                break
            if release_group is None:
                release_group = rg.group(1)
            work = RELEASE_GROUP_PATTERN.sub("", work)

        # 把分隔符变空格
        work = re.sub(r"[._]+", " ", work)
        # 折叠空白
        work = re.sub(r"\s+", " ", work).strip()
        # 去掉首尾的破折号
        work = work.strip("-").strip()

        title = work or p.title or p.raw  # 如果清理过头,回退到上游产物或原始名
        normalized = re.sub(r"\s+", "", title.lower())

        return ParsedName(
            raw=p.raw,
            working=title,
            title=title,
            normalized_title=normalized,
            year=year,
            season=season,
            episode=episode,
            quality=quality,
            release_group=release_group,
            language_tags=p.language_tags + lang_tags,
            applied=p.applied + [self.name],
        )
