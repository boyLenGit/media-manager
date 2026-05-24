"""文件名解析:从文件名提取规范化标题、清晰度、编码、年份等。

第一版用简单正则,目标是把发布组/编码标记/分辨率剥离掉,留下可读标题。
不追求完美,后续可换 anitomy / parse-torrent-name 等专用库。
"""
import re
from dataclasses import dataclass


# 常见垃圾标记(顺序敏感:先去精确的,再去模糊的)
RESOLUTION_PATTERNS = [
    r"\b(?:480|540|576|720|1080|1440|2160|4320)[pi]\b",
    r"\b4K\b",
    r"\b8K\b",
    r"\bUHD\b",
    r"\bHD\b",
    r"\bFHD\b",
    r"\bSD\b",
]

CODEC_PATTERNS = [
    r"\bH\.?264\b",
    r"\bH\.?265\b",
    r"\bx264\b",
    r"\bx265\b",
    r"\bHEVC\b",
    r"\bAVC\b",
    r"\bAV1\b",
    r"\bVP9\b",
    r"\bAAC\b",
    r"\bAC3\b",
    r"\bDTS(?:-HD)?\b",
    r"\bFLAC\b",
    r"\bMP3\b",
    r"\b10[Bb]it\b",
    r"\b8[Bb]it\b",
]

SOURCE_PATTERNS = [
    r"\bBluRay\b",
    r"\bBDRip\b",
    r"\bBRRip\b",
    r"\bWEB-?DL\b",
    r"\bWEBRip\b",
    r"\bHDTV\b",
    r"\bDVDRip\b",
    r"\bRemux\b",
]

LANG_PATTERNS = [
    r"\b(?:CHS|CHT|JPN|ENG|KOR|GB|BIG5)\b",
    r"简(?:体)?(?:中文)?",
    r"繁(?:体)?(?:中文)?",
    r"国(?:语|配)",
    r"粤(?:语)?",
    r"英语",
    r"日语",
    r"中(?:文)?字幕",
    r"中字",
    r"双语",
]

YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")
SEASON_EPISODE_PATTERN = re.compile(r"\b[Ss](\d{1,2})[Ee](\d{1,3})\b")

# 发布组通常在方括号里,或 -GROUP_NAME 后缀
RELEASE_GROUP_PATTERN = re.compile(r"-([A-Za-z0-9]{2,12})$")


@dataclass
class ParsedName:
    raw: str  # 原始文件名(去扩展名)
    title: str  # 清理后的标题
    normalized_title: str  # 用于去重比对(小写、去空格)
    year: int | None = None
    season: int | None = None
    episode: int | None = None
    quality: str | None = None  # "1080p" / "4K" 等
    release_group: str | None = None


def _strip_brackets_groups(s: str) -> str:
    """剥离 [发布组] 前缀和 [...] 内嵌标记。保留主体文本。"""
    # 移除 [...] (...) {...}
    s = re.sub(r"\[[^\]]*\]", " ", s)
    s = re.sub(r"\([^\)]*\)", " ", s)
    s = re.sub(r"\{[^\}]*\}", " ", s)
    return s


def _extract_quality(s: str) -> str | None:
    for pat in RESOLUTION_PATTERNS:
        m = re.search(pat, s, re.IGNORECASE)
        if m:
            return m.group(0)
    return None


def parse_filename(filename_no_ext: str) -> ParsedName:
    """解析文件名(不含扩展名),返回结构化数据。"""
    raw = filename_no_ext
    work = filename_no_ext

    # 提取年份
    year = None
    m = YEAR_PATTERN.search(work)
    if m:
        year = int(m.group(1))

    # 提取季/集
    season = episode = None
    m = SEASON_EPISODE_PATTERN.search(work)
    if m:
        season = int(m.group(1))
        episode = int(m.group(2))

    # 提取清晰度(在剥离之前)
    quality = _extract_quality(work)

    # 剥离方括号
    work = _strip_brackets_groups(work)

    # 剥离编码/分辨率/来源/语言标记
    for pat_list in (RESOLUTION_PATTERNS, CODEC_PATTERNS, SOURCE_PATTERNS, LANG_PATTERNS):
        for pat in pat_list:
            work = re.sub(pat, " ", work, flags=re.IGNORECASE)

    # 剥离年份
    work = YEAR_PATTERN.sub(" ", work)

    # 剥离季/集
    work = SEASON_EPISODE_PATTERN.sub(" ", work)

    # 提取发布组(在剥离前先记录)
    release_group = None
    rg_match = RELEASE_GROUP_PATTERN.search(work)
    if rg_match:
        release_group = rg_match.group(1)
        work = RELEASE_GROUP_PATTERN.sub("", work)

    # 把 . _ 当空格
    work = re.sub(r"[._]+", " ", work)
    # 折叠空白
    work = re.sub(r"\s+", " ", work).strip()
    # 去掉首尾的破折号
    work = work.strip("-").strip()

    title = work or raw  # 若清理过头,回退到原始
    normalized = re.sub(r"\s+", "", title.lower())

    return ParsedName(
        raw=raw,
        title=title,
        normalized_title=normalized,
        year=year,
        season=season,
        episode=episode,
        quality=quality,
        release_group=release_group,
    )
