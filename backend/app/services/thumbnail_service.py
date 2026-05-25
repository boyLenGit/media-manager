"""缩略图管理。

存储位置: data/thumbnails/<media_id>.jpg
通过 /api/thumbnails/<media_id>.jpg 提供静态访问 (不需要鉴权,因为这是图片资源,且文件名就是 media_id)。
"""
from pathlib import Path

from app.core.config import get_settings


def get_thumbnail_dir() -> Path:
    settings = get_settings()
    d = settings.data_dir / "thumbnails"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_thumbnail_path(media_id: int) -> Path:
    return get_thumbnail_dir() / f"{media_id}.jpg"


def get_thumbnail_url(media_id: int) -> str:
    """供 cover_path 字段使用的相对 URL。"""
    return f"/api/thumbnails/{media_id}.jpg"


def has_thumbnail(media_id: int) -> bool:
    p = get_thumbnail_path(media_id)
    return p.exists() and p.stat().st_size > 0
