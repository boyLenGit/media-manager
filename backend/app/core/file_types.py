"""文件类型常量与扩展名分类。"""

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".ts", ".m2ts", ".flv", ".wmv"}
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".vtt", ".ssa", ".sub"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
METADATA_EXTENSIONS = {".nfo", ".json", ".xml"}

ALL_KNOWN = VIDEO_EXTENSIONS | SUBTITLE_EXTENSIONS | IMAGE_EXTENSIONS | METADATA_EXTENSIONS

# 浏览器原生可直放的容器
WEB_PLAYABLE_CONTAINERS = {".mp4", ".webm", ".m4v"}


def classify_file(extension: str) -> str | None:
    """返回 'video' / 'subtitle' / 'image' / 'metadata' / None。"""
    ext = extension.lower()
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in SUBTITLE_EXTENSIONS:
        return "subtitle"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    if ext in METADATA_EXTENSIONS:
        return "metadata"
    return None


def is_web_playable(extension: str) -> bool:
    return extension.lower() in WEB_PLAYABLE_CONTAINERS
