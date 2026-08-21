"""自定义字幕文件存储管理。

存储位置: data/custom_subtitles/<custom_subtitle_id>.<ext>
通过 /api/custom-subtitles/{id}/stream?token=... 提供访问(和视频一样走签名 token,
不像缩略图/作者封面那样完全公开 —— 字幕内容能反映用户在看什么,不适合裸暴露)。

与自动扫描发现的字幕(file_asset 表,来自扫描目录)不同:
- 自定义字幕是用户主动上传的附属资源,不占用只读挂载的视频目录
- 上传时立即做编码检测转 UTF-8(复用 subtitle_encoding 模块)后落盘,
  存储的内容永远是规范 UTF-8,访问时不需要二次转码
"""
from pathlib import Path

from app.core.config import get_settings

ALLOWED_EXTENSIONS = {"srt", "ass", "ssa", "vtt"}

CONTENT_TYPE_EXT_MAP = {
    "application/x-subrip": "srt",
    "text/srt": "srt",
    "text/x-ass": "ass",
    "text/x-ssa": "ssa",
    "text/vtt": "vtt",
    # 很多浏览器/系统对字幕文件没有注册明确 MIME,回退成通用类型,
    # 这种情况下用文件名后缀而不是 content_type 判断(见 api 层)
    "application/octet-stream": "",
    "text/plain": "",
}


def get_custom_subtitle_dir() -> Path:
    settings = get_settings()
    d = settings.data_dir / "custom_subtitles"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_custom_subtitle_path(subtitle_id: int, ext: str) -> Path:
    return get_custom_subtitle_dir() / f"{subtitle_id}.{ext}"


def delete_custom_subtitle_file(subtitle_id: int) -> None:
    """删除该字幕记录对应的物理文件(任意允许的扩展名都尝试删除,避免残留)。"""
    d = get_custom_subtitle_dir()
    for ext in ALLOWED_EXTENSIONS:
        p = d / f"{subtitle_id}.{ext}"
        if p.exists():
            p.unlink()


def ext_from_filename(filename: str) -> str | None:
    """从原始上传文件名推断规范化扩展名(不含点,小写)。"""
    suffix = Path(filename).suffix.lower().lstrip(".")
    return suffix if suffix in ALLOWED_EXTENSIONS else None
