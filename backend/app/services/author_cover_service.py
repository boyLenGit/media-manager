"""作者封面图管理。

存储位置: data/author_covers/<author_id>.<ext>
通过 /api/author-covers/<author_id>.<ext> 提供静态访问(公开,不需要鉴权,风格对齐 thumbnails)。

与 media 缩略图不同:作者封面是用户手动上传的,不会被扫描流程自动生成/覆盖。
"""
from pathlib import Path

from app.core.config import get_settings

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}

CONTENT_TYPE_EXT_MAP = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def get_author_cover_dir() -> Path:
    settings = get_settings()
    d = settings.data_dir / "author_covers"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_author_cover_path(author_id: int, ext: str) -> Path:
    return get_author_cover_dir() / f"{author_id}.{ext}"


def get_author_cover_url(author_id: int, ext: str) -> str:
    """供 cover_path 字段使用的相对 URL。"""
    return f"/api/author-covers/{author_id}.{ext}"


def find_existing_cover(author_id: int) -> Path | None:
    """按任意允许的扩展名查找该作者当前是否已有封面文件。"""
    d = get_author_cover_dir()
    for ext in ALLOWED_EXTENSIONS:
        p = d / f"{author_id}.{ext}"
        if p.exists():
            return p
    return None


def delete_author_cover(author_id: int) -> None:
    """删除该作者所有可能扩展名的封面文件(避免更换格式后残留旧文件)。"""
    d = get_author_cover_dir()
    for ext in ALLOWED_EXTENSIONS:
        p = d / f"{author_id}.{ext}"
        if p.exists():
            p.unlink()
