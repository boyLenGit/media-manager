"""缩略图静态接口。

不需要鉴权(图片资源,资源 ID 在公开 API 里也能查到)。
路径限定在 data/thumbnails/ 目录下,严格校验文件名为 数字.jpg 防止路径穿越。
"""
import re

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services import thumbnail_service

router = APIRouter()

_FILENAME_RE = re.compile(r"^(\d+)\.jpg$")


@router.get("/{filename}")
def get_thumbnail(filename: str):
    m = _FILENAME_RE.match(filename)
    if not m:
        raise HTTPException(status_code=400, detail="invalid_filename")

    media_id = int(m.group(1))
    path = thumbnail_service.get_thumbnail_path(media_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail="thumbnail_not_found")
    return FileResponse(
        path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400"},
    )
