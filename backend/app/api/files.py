"""文件接口。

- 列表/详情/probe:走标准 access token 鉴权
- /stream:走短期签名 token (query 参数),供 <video> 标签使用
- /stream-token:用 access token 换签名 URL
- /subtitles:同名字幕识别
"""
from pathlib import Path

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from app.core.deps import require_user
from app.core.file_types import SUBTITLE_EXTENSIONS, is_web_playable
from app.core.security import create_stream_token, verify_stream_token
from app.core.streaming import make_file_response, make_subtitle_response
from app.db.session import get_session
from app.models import FileAsset, MediaFile, User
from app.services.filename_parser import parse_filename

router = APIRouter()


# ============================================================
# 流签名 (require_user)
# ============================================================
@router.get("/{file_id}/stream-token")
def get_stream_token(
    file_id: int,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict:
    asset = session.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(status_code=404, detail="file_not_found")
    token = create_stream_token(user.id, file_id, ttl_minutes=60)  # type: ignore[arg-type]
    return {
        "token": token,
        "url": f"/api/files/{file_id}/stream?token={token}",
        "expires_in": 3600,
    }


# ============================================================
# 流接口 (无 require_user 依赖,自己用签名 token 鉴权)
# ============================================================
@router.get("/{file_id}/stream")
@router.head("/{file_id}/stream")
def stream_file(
    file_id: int,
    request: Request,
    token: str = Query(..., description="stream token from /stream-token"),
    session: Session = Depends(get_session),
):
    try:
        verify_stream_token(token, file_id)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="stream_token_expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid_stream_token")

    asset = session.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(status_code=404, detail="file_not_found")
    if asset.missing:
        raise HTTPException(status_code=410, detail="file_missing")

    # 字幕文件走独立响应:自动检测源编码(GBK/Big5/Shift-JIS 等)并统一转成 UTF-8,
    # 避免浏览器按 UTF-8 解码非 UTF-8 字幕产生静默乱码。
    ext = (asset.extension or "").lower()
    if ext in SUBTITLE_EXTENSIONS:
        return make_subtitle_response(asset.path, request=request)

    return make_file_response(request, asset.path, filename=asset.filename)


# ============================================================
# 字幕识别 (require_user)
# ============================================================
@router.get("/{file_id}/subtitles")
def list_subtitles(
    file_id: int,
    _user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[dict]:
    """返回与目标视频文件同目录、推测同源的字幕文件列表。

    匹配规则(按优先级):
    1. 字幕 stem 完全等于视频 stem (movie.mkv + movie.srt)
    2. 字幕 stem 以视频 stem 开头 (movie.mkv + movie.zh.srt)
    3. 解析后 normalized_title 相同 (Inception.2010.1080p.mp4 + Inception.2010.zh.srt)
    """
    video = session.get(FileAsset, file_id)
    if not video:
        raise HTTPException(status_code=404, detail="file_not_found")
    if video.file_type != "video":
        return []

    video_stem = Path(video.filename).stem
    video_norm = parse_filename(video_stem).normalized_title
    directory = video.directory or str(Path(video.path).parent)

    candidates = session.exec(
        select(FileAsset).where(
            FileAsset.directory == directory,
            FileAsset.file_type == "subtitle",
            FileAsset.missing == False,  # noqa: E712
        )
    ).all()

    out: list[dict] = []
    for s in candidates:
        s_stem = Path(s.filename).stem
        match_kind = None
        language_hint = None

        if s_stem == video_stem:
            match_kind = "exact"
        elif s_stem.startswith(video_stem + "."):
            match_kind = "prefix"
            language_hint = s_stem[len(video_stem) + 1 :]
        else:
            # 用规范化标题比对
            s_norm = parse_filename(s_stem).normalized_title
            if s_norm and video_norm and (s_norm == video_norm or s_norm.startswith(video_norm)):
                match_kind = "normalized"
                # 尝试从字幕 stem 提取语言段(简单启发)
                tail = s_stem.split(".")[-1]
                if 2 <= len(tail) <= 6 and tail.lower() in (
                    "zh", "cn", "chs", "cht", "tc", "sc", "en", "eng", "ja", "jp", "jpn",
                    "ko", "kor", "fr", "de", "es", "ru",
                ):
                    language_hint = tail.lower()

        if match_kind:
            out.append(
                {
                    "id": s.id,
                    "filename": s.filename,
                    "extension": s.extension,
                    "language_hint": language_hint,
                    "match": match_kind,
                    "url": f"/api/files/{s.id}/stream",  # 字幕也走 stream-token
                }
            )
    return out


# ============================================================
# 探测 (require_user)
# ============================================================
@router.get("/{file_id}/probe")
def probe_file(
    file_id: int,
    _user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict:
    asset = session.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(status_code=404, detail="file_not_found")
    return {
        "id": asset.id,
        "path": asset.path,
        "filename": asset.filename,
        "size_bytes": asset.size_bytes,
        "file_type": asset.file_type,
        "extension": asset.extension,
        "partial_hash": asset.partial_hash,
        "media_probe_json": asset.media_probe_json,
        "missing": asset.missing,
    }


# ============================================================
# 元数据辅助 (前端判断是否 web 可播)
# ============================================================
@router.get("/{file_id}")
def get_file_meta(
    file_id: int,
    _user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict:
    asset = session.get(FileAsset, file_id)
    if not asset:
        raise HTTPException(status_code=404, detail="file_not_found")

    mf = session.exec(select(MediaFile).where(MediaFile.file_asset_id == file_id)).first()
    return {
        "id": asset.id,
        "filename": asset.filename,
        "extension": asset.extension,
        "size_bytes": asset.size_bytes,
        "file_type": asset.file_type,
        "missing": asset.missing,
        "web_playable": is_web_playable(asset.extension or "") if asset.extension else False,
        "media_file": (
            {
                "id": mf.id,
                "media_item_id": mf.media_item_id,
                "duration_seconds": mf.duration_seconds,
                "width": mf.width,
                "height": mf.height,
                "video_codec": mf.video_codec,
                "audio_codec": mf.audio_codec,
            }
            if mf
            else None
        ),
    }
