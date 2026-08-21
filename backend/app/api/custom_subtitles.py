"""自定义字幕管理(用户手动上传/替换字幕)。

设计:
- 与 files.py::list_subtitles() 的"同目录文件名自动匹配"机制并存、互不冲突。
  自定义字幕是持久化记录,精确绑定到 file_asset_id,不依赖文件名规则。
- 上传时立即用 subtitle_encoding 模块做编码检测,统一转成 UTF-8 后落盘存储,
  避免用户上传 GBK/Big5 等编码的字幕在播放时产生乱码。
- 播放走签名 token(类似视频 /stream),不像缩略图/作者封面那样公开,
  因为字幕内容能反映用户在看什么。
"""
from datetime import datetime

import jwt
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlmodel import Session, select
from starlette.responses import Response

from app.core.security import create_custom_subtitle_token, verify_custom_subtitle_token
from app.core.deps import require_user
from app.core.streaming import MIME_MAP
from app.db.session import get_session
from app.models import CustomSubtitle, FileAsset, User
from app.services import custom_subtitle_service
from app.services.subtitle_encoding import normalize_subtitle_to_utf8

router = APIRouter()

MAX_SUBTITLE_SIZE_BYTES = 5 * 1024 * 1024  # 5MB,字幕文件正常几十 KB,给足余量


class CustomSubtitleOut(BaseModel):
    id: int
    file_asset_id: int
    filename: str
    extension: str
    language_hint: str | None = None
    size_bytes: int | None = None
    created_at: datetime
    updated_at: datetime


def _to_out(s: CustomSubtitle) -> CustomSubtitleOut:
    return CustomSubtitleOut(
        id=s.id,  # type: ignore[arg-type]
        file_asset_id=s.file_asset_id,
        filename=s.filename,
        extension=s.extension,
        language_hint=s.language_hint,
        size_bytes=s.size_bytes,
        created_at=s.created_at,
        updated_at=s.updated_at,
    )


# ============================================================
# 列表 (require_user)
# ============================================================
@router.get("/by-file/{file_asset_id}")
def list_custom_subtitles(
    file_asset_id: int,
    _user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[CustomSubtitleOut]:
    video = session.get(FileAsset, file_asset_id)
    if not video:
        raise HTTPException(status_code=404, detail="file_not_found")
    rows = session.exec(
        select(CustomSubtitle)
        .where(CustomSubtitle.file_asset_id == file_asset_id)
        .order_by(CustomSubtitle.created_at.desc())  # type: ignore[union-attr]
    ).all()
    return [_to_out(s) for s in rows]


# ============================================================
# 上传 (require_user)
# ============================================================
@router.post("/by-file/{file_asset_id}")
async def upload_custom_subtitle(
    file_asset_id: int,
    file: UploadFile = File(...),
    language_hint: str | None = None,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> CustomSubtitleOut:
    video = session.get(FileAsset, file_asset_id)
    if not video:
        raise HTTPException(status_code=404, detail="file_not_found")

    filename = file.filename or "subtitle"
    ext = custom_subtitle_service.ext_from_filename(filename)
    if not ext:
        raise HTTPException(status_code=400, detail="unsupported_subtitle_type")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty_file")
    if len(raw) > MAX_SUBTITLE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="file_too_large")

    # 编码检测转 UTF-8(vtt/ass/ssa/srt 均走文本规范化;存储的是转换后的内容)
    normalized = normalize_subtitle_to_utf8(raw)

    obj = CustomSubtitle(
        file_asset_id=file_asset_id,
        filename=filename,
        extension=ext,
        language_hint=language_hint,
        size_bytes=len(normalized),
        created_by=user.id,
    )
    session.add(obj)
    session.commit()
    session.refresh(obj)

    path = custom_subtitle_service.get_custom_subtitle_path(obj.id, ext)  # type: ignore[arg-type]
    path.write_bytes(normalized)

    return _to_out(obj)


# ============================================================
# 删除 (require_user)
# ============================================================
@router.delete("/{subtitle_id}", status_code=204)
def delete_custom_subtitle(
    subtitle_id: int,
    _user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> None:
    obj = session.get(CustomSubtitle, subtitle_id)
    if not obj:
        raise HTTPException(status_code=404, detail="subtitle_not_found")
    custom_subtitle_service.delete_custom_subtitle_file(subtitle_id)
    session.delete(obj)
    session.commit()


# ============================================================
# 流签名 (require_user)
# ============================================================
@router.get("/{subtitle_id}/stream-token")
def get_custom_subtitle_token(
    subtitle_id: int,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict:
    obj = session.get(CustomSubtitle, subtitle_id)
    if not obj:
        raise HTTPException(status_code=404, detail="subtitle_not_found")
    token = create_custom_subtitle_token(user.id, subtitle_id, ttl_minutes=60)  # type: ignore[arg-type]
    return {
        "token": token,
        "url": f"/api/custom-subtitles/{subtitle_id}/stream?token={token}",
        "expires_in": 3600,
    }


# ============================================================
# 播放访问 (无 require_user 依赖,自己用签名 token 鉴权;已是规范 UTF-8,直接原样返回)
# ============================================================
@router.get("/{subtitle_id}/stream")
@router.head("/{subtitle_id}/stream")
def stream_custom_subtitle(
    subtitle_id: int,
    request: Request,
    token: str = Query(..., description="stream token from /stream-token"),
    session: Session = Depends(get_session),
):
    try:
        verify_custom_subtitle_token(token, subtitle_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="stream_token_expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid_stream_token")

    obj = session.get(CustomSubtitle, subtitle_id)
    if not obj:
        raise HTTPException(status_code=404, detail="subtitle_not_found")

    path = custom_subtitle_service.get_custom_subtitle_path(subtitle_id, obj.extension)
    if not path.exists():
        raise HTTPException(status_code=404, detail="file_missing")

    mime = MIME_MAP.get(f".{obj.extension}", "text/plain")
    if request.method == "HEAD":
        return Response(
            status_code=200, headers={"Cache-Control": "private, max-age=0"}, media_type=mime
        )

    data = path.read_bytes()
    return Response(
        content=data,
        status_code=200,
        headers={
            "Content-Length": str(len(data)),
            "Cache-Control": "private, max-age=0",
            "Content-Type": f"{mime}; charset=utf-8",
        },
        media_type=mime,
    )
