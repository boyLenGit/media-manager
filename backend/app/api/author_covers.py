"""作者封面图静态接口。

不需要鉴权(图片资源,作者信息本身也不敏感)。
路径限定在 data/author_covers/ 目录下,严格校验文件名为 数字.扩展名 防止路径穿越。
"""
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services import author_cover_service

router = APIRouter()

_FILENAME_RE = re.compile(r"^(\d+)\.(jpg|jpeg|png|webp)$")

_MEDIA_TYPE_MAP = {
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
}


@router.get("/{filename}")
def get_author_cover(filename: str):
    m = _FILENAME_RE.match(filename)
    if not m:
        raise HTTPException(status_code=400, detail="invalid_filename")

    author_id = int(m.group(1))
    ext = m.group(2)
    path = author_cover_service.get_author_cover_path(author_id, ext)
    if not path.exists():
        raise HTTPException(status_code=404, detail="cover_not_found")
    return FileResponse(
        path,
        media_type=_MEDIA_TYPE_MAP.get(ext, "application/octet-stream"),
        headers={"Cache-Control": "public, max-age=86400"},
    )
