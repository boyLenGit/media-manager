"""文件类型常量与扩展名分类。

注意:`is_web_playable_by_ext` 仅做"扩展名层级的初步判断"。
精确的可播性必须看 codec(用 ffprobe_service.is_codec_web_playable)。
原因:.mp4 容器内可能装着浏览器不支持的 mpeg4(Part 2)、HEVC 等编码。
"""

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".ts", ".m2ts", ".flv", ".wmv"}
SUBTITLE_EXTENSIONS = {".srt", ".ass", ".vtt", ".ssa", ".sub"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
METADATA_EXTENSIONS = {".nfo", ".json", ".xml"}

ALL_KNOWN = VIDEO_EXTENSIONS | SUBTITLE_EXTENSIONS | IMAGE_EXTENSIONS | METADATA_EXTENSIONS

# 浏览器原生支持的容器(粗判,真实可播性还要看 codec)
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


def is_web_playable_by_ext(extension: str) -> bool:
    """仅看扩展名的可播性判断,容器对了不代表 codec 也对。"""
    return extension.lower() in WEB_PLAYABLE_CONTAINERS


# 兼容旧名字
def is_web_playable(extension: str) -> bool:
    return is_web_playable_by_ext(extension)
