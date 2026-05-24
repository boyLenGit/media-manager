"""播放选项接口。

play-options 根据资源关联的主文件,智能返回当前可用的播放选项:
- web: 仅当文件容器为浏览器原生支持时才返回 (mp4/webm/m4v)
- jellyfin: 仅当配置了 Jellyfin 时返回
- external_url / smb_path: 总是可用 (复制链接)
- reveal_dir: 复制目录路径
"""
import json
from datetime import datetime
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.core.config import get_settings
from app.core.deps import require_user
from app.core.file_types import is_web_playable
from app.db.session import get_session
from app.models import (
    AppSetting,
    FileAsset,
    MediaFile,
    MediaItem,
    PlaybackHistory,
    PlaybackTarget,
    User,
)
from app.providers.player import factory as jellyfin_factory

router = APIRouter()


# ============================================================
# 播放目标管理
# ============================================================
@router.get("/targets")
def list_targets(session: Session = Depends(get_session)) -> list[PlaybackTarget]:
    stmt = select(PlaybackTarget).order_by(PlaybackTarget.sort_order)  # type: ignore[union-attr]
    return session.exec(stmt).all()


@router.patch("/targets/{target_id}")
def update_target(
    target_id: int, payload: dict, session: Session = Depends(get_session)
) -> PlaybackTarget:
    obj = session.get(PlaybackTarget, target_id)
    if not obj:
        raise HTTPException(status_code=404, detail="target_not_found")
    for k in ("name", "enabled", "sort_order", "config_json"):
        if k in payload:
            setattr(obj, k, payload[k])
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


# ============================================================
# 辅助:从 app_setting 读取配置
# ============================================================
def _get_setting(session: Session, key: str, default: str = "") -> str:
    s = session.exec(select(AppSetting).where(AppSetting.key == key)).first()
    return s.value or default if s else default


def _smb_url_for(path: str, smb_host: str, smb_share_map: dict[str, str]) -> str | None:
    """根据 path 找到对应的 SMB 共享名,生成 smb:// URL。

    smb_share_map 形如 {"/volume1/media": "media"}
    """
    if not smb_host:
        return None
    for local_root, share_name in smb_share_map.items():
        if path.startswith(local_root):
            relative = path[len(local_root) :].lstrip("/")
            return f"smb://{smb_host}/{share_name}/{relative}"
    return None


# ============================================================
# 资源播放选项
# ============================================================
@router.get("/media/{media_id}/options")
def get_play_options(media_id: int, session: Session = Depends(get_session)) -> dict:
    media = session.get(MediaItem, media_id)
    if not media:
        raise HTTPException(status_code=404, detail="media_not_found")

    # 取所有视频文件
    rows = session.exec(
        select(MediaFile, FileAsset)
        .join(FileAsset, FileAsset.id == MediaFile.file_asset_id)  # type: ignore[arg-type]
        .where(MediaFile.media_item_id == media_id)
        .order_by(MediaFile.is_primary.desc(), MediaFile.id)  # type: ignore[union-attr]
    ).all()

    if not rows:
        return {"media_id": media_id, "files": [], "options": []}

    settings = get_settings()
    targets = session.exec(
        select(PlaybackTarget)
        .where(PlaybackTarget.enabled == True)  # noqa: E712
        .order_by(PlaybackTarget.sort_order)  # type: ignore[union-attr]
    ).all()

    smb_host = _get_setting(session, "smb_host", "")
    try:
        smb_share_map = json.loads(_get_setting(session, "smb_share_map", "{}"))
    except json.JSONDecodeError:
        smb_share_map = {}

    # Jellyfin 配置(支持 UI 修改优先,否则用 env)
    jf_cfg = jellyfin_factory.read_config()
    jellyfin_url = jf_cfg.get("url", "")

    files_payload: list[dict] = []
    for mf, fa in rows:
        web_ok = is_web_playable(fa.extension or "") and not fa.missing

        opts: list[dict] = []
        for t in targets:
            url = _build_url(t, fa, media, settings, smb_host, smb_share_map, web_ok, jellyfin_url)
            if url is None:
                continue
            opts.append(
                {
                    "type": t.target_type,
                    "label": t.name,
                    "url": url,
                    "available": True,
                }
            )

        files_payload.append(
            {
                "file_asset_id": fa.id,
                "filename": fa.filename,
                "extension": fa.extension,
                "missing": fa.missing,
                "is_primary": mf.is_primary,
                "quality": mf.quality,
                "container": mf.container,
                "duration_seconds": mf.duration_seconds,
                "width": mf.width,
                "height": mf.height,
                "web_playable": web_ok,
                "options": opts,
            }
        )

    primary = files_payload[0]
    return {
        "media_id": media_id,
        "files": files_payload,
        "options": primary["options"],
    }


def _build_url(
    t: PlaybackTarget,
    fa: FileAsset,
    media: MediaItem,
    settings,
    smb_host: str,
    smb_share_map: dict[str, str],
    web_ok: bool,
    jellyfin_url: str,
) -> str | None:
    """根据目标类型返回 URL,无法生成时返回 None(该选项不显示)。"""
    if t.target_type == "web":
        if not web_ok:
            return None
        return f"/api/files/{fa.id}/stream"

    if t.target_type == "external_url":
        return f"/api/files/{fa.id}/stream"

    if t.target_type == "smb_path":
        return _smb_url_for(fa.path, smb_host, smb_share_map)

    if t.target_type == "jellyfin":
        if not jellyfin_url:
            return None
        # 先返回搜索页 URL(用 media 标题搜),后续可改为精确 ItemId 跳转
        return f"{jellyfin_url.rstrip('/')}/web/#/search.html?query={quote(media.title)}"

    if t.target_type == "reveal_dir":
        return fa.directory or ""

    if t.target_type == "custom_protocol":
        scheme = "mediahub"
        if t.config_json:
            try:
                cfg = json.loads(t.config_json)
                scheme = cfg.get("scheme", scheme)
            except json.JSONDecodeError:
                pass
        return f"{scheme}://play?path={fa.path}"

    return None


# ============================================================
# 播放历史
# ============================================================
class PlaybackProgressIn(BaseModel):
    media_item_id: int
    file_asset_id: int | None = None
    playback_target_id: int | None = None
    position_seconds: float = Field(ge=0)
    duration_seconds: float | None = None
    completed: bool = False


@router.post("/progress", status_code=201)
def report_progress(
    payload: PlaybackProgressIn,
    user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict:
    """前端定时(每 15s)上报播放进度。

    简单策略:每次都新插一条记录,详情页查最近一条作为续播位置。
    后续可优化为按 (user, media, file) upsert,但当前简单设计利于多设备播放历史。
    """
    h = PlaybackHistory(
        media_item_id=payload.media_item_id,
        file_asset_id=payload.file_asset_id,
        playback_target_id=payload.playback_target_id,
        position_seconds=payload.position_seconds,
        duration_seconds=payload.duration_seconds,
        completed=payload.completed,
    )
    session.add(h)

    # 完成播放自动更新观看状态
    if payload.completed:
        media = session.get(MediaItem, payload.media_item_id)
        if media and media.watch_status != "watched":
            media.watch_status = "watched"
            media.updated_at = datetime.utcnow()
            session.add(media)

    session.commit()
    session.refresh(h)
    return {"id": h.id, "position_seconds": h.position_seconds}


@router.get("/media/{media_id}/history")
def get_media_history(
    media_id: int,
    limit: int = 20,
    _user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> list[PlaybackHistory]:
    return session.exec(
        select(PlaybackHistory)
        .where(PlaybackHistory.media_item_id == media_id)
        .order_by(PlaybackHistory.id.desc())  # type: ignore[union-attr]
        .limit(limit)
    ).all()


@router.get("/media/{media_id}/resume")
def get_resume_position(
    media_id: int,
    file_asset_id: int | None = None,
    _user: User = Depends(require_user),
    session: Session = Depends(get_session),
) -> dict:
    """返回最近一次未完成的播放位置,用于续播。"""
    stmt = (
        select(PlaybackHistory)
        .where(
            PlaybackHistory.media_item_id == media_id,
            PlaybackHistory.completed == False,  # noqa: E712
        )
        .order_by(PlaybackHistory.id.desc())  # type: ignore[union-attr]
    )
    if file_asset_id is not None:
        stmt = stmt.where(PlaybackHistory.file_asset_id == file_asset_id)
    h = session.exec(stmt).first()
    if not h:
        return {"position_seconds": 0, "duration_seconds": None}
    return {
        "position_seconds": h.position_seconds,
        "duration_seconds": h.duration_seconds,
        "file_asset_id": h.file_asset_id,
        "played_at": h.played_at.isoformat() + "Z" if h.played_at else None,
    }
