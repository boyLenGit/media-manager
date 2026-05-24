"""下载任务接口。

设计:
- 创建任务前先调用去重服务,客户端可选择 force=true 跳过提示
- 状态由 download_status_sync 后台任务定期同步
- 下载完成后由 download_complete_handler 处理入库
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.db.session import get_session
from app.models import DownloadTask, SearchResult
from app.providers.downloader import factory as downloader_factory
from app.services.duplicate_service import detect_search_result_duplicate

router = APIRouter()


class DuplicateInfo(BaseModel):
    level: str
    reason: str
    matched_media_id: int | None = None
    matched_file_id: int | None = None
    score: float = 0.0


class CheckDuplicateIn(BaseModel):
    title: str
    info_hash: str | None = None
    magnet_uri: str | None = None
    size_bytes: int | None = None


class CreateDownloadIn(BaseModel):
    title: str = Field(..., min_length=1)
    magnet_uri: str = Field(..., min_length=1)
    info_hash: str | None = None
    save_path: str | None = None
    search_result_id: int | None = None
    force: bool = False  # 跳过去重提示


@router.get("/config")
def get_config() -> dict:
    """返回当前下载器配置(脱敏)。"""
    cfg = downloader_factory._read_setting()  # type: ignore[attr-defined]
    return {
        "provider": cfg.get("provider", "qbittorrent"),
        "url": cfg.get("url") or "",
        "username": cfg.get("username") or "",
        "password_set": bool(cfg.get("password")),
        "configured": bool(cfg.get("url") and cfg.get("username")),
    }


class UpdateConfigIn(BaseModel):
    provider: str = "qbittorrent"
    url: str
    username: str
    password: str | None = None  # None = 保持不变


@router.put("/config")
def update_config(payload: UpdateConfigIn) -> dict:
    cfg = downloader_factory._read_setting()  # type: ignore[attr-defined]
    new_cfg = {
        "provider": payload.provider,
        "url": payload.url.rstrip("/"),
        "username": payload.username,
        "password": payload.password if payload.password is not None else cfg.get("password", ""),
    }
    downloader_factory.save_setting(new_cfg)
    return {"status": "saved"}


@router.post("/test")
async def test_connection() -> dict:
    return await downloader_factory.health_check()


# ============================================================
# 去重检测
# ============================================================
@router.post("/check-duplicate")
def check_duplicate(
    payload: CheckDuplicateIn, session: Session = Depends(get_session)
) -> DuplicateInfo:
    r = detect_search_result_duplicate(
        session,
        title=payload.title,
        info_hash=payload.info_hash,
        magnet_uri=payload.magnet_uri,
        size_bytes=payload.size_bytes,
    )
    return DuplicateInfo(
        level=r.level,
        reason=r.reason,
        matched_media_id=r.matched_media_id,
        matched_file_id=r.matched_file_id,
        score=r.score,
    )


# ============================================================
# 任务列表
# ============================================================
@router.get("")
def list_downloads(
    status: str | None = None,
    limit: int = 100,
    session: Session = Depends(get_session),
) -> list[DownloadTask]:
    stmt = select(DownloadTask).order_by(DownloadTask.id.desc())  # type: ignore[union-attr]
    if status:
        stmt = stmt.where(DownloadTask.status == status)
    return session.exec(stmt.limit(limit)).all()


@router.get("/{task_id}")
def get_download(task_id: int, session: Session = Depends(get_session)) -> DownloadTask:
    obj = session.get(DownloadTask, task_id)
    if not obj:
        raise HTTPException(status_code=404, detail="task_not_found")
    return obj


# ============================================================
# 创建任务
# ============================================================
@router.post("", status_code=201)
async def create_download(
    payload: CreateDownloadIn, session: Session = Depends(get_session)
) -> dict:
    if not downloader_factory.is_configured():
        raise HTTPException(status_code=400, detail="downloader_not_configured")

    # 1. 去重检查
    dup = detect_search_result_duplicate(
        session,
        title=payload.title,
        info_hash=payload.info_hash,
        magnet_uri=payload.magnet_uri,
    )
    if dup.level in ("exact", "high") and not payload.force:
        return {
            "status": "duplicate",
            "duplicate": DuplicateInfo(
                level=dup.level,
                reason=dup.reason,
                matched_media_id=dup.matched_media_id,
                matched_file_id=dup.matched_file_id,
                score=dup.score,
            ).model_dump(),
            "hint": "使用 force=true 强制下载",
        }

    # 2. 调下载器
    provider = downloader_factory.create_provider()
    if not provider:
        raise HTTPException(status_code=500, detail="downloader_create_failed")

    try:
        task_id_in_downloader = await provider.add_magnet(
            payload.magnet_uri, save_path=payload.save_path
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"downloader_error: {e}")
    finally:
        await provider.close()  # type: ignore[union-attr]

    # 3. 入库
    db_task = DownloadTask(
        search_result_id=payload.search_result_id,
        title=payload.title,
        magnet_uri=payload.magnet_uri,
        info_hash=(payload.info_hash or task_id_in_downloader).lower(),
        downloader="qbittorrent",
        downloader_task_id=task_id_in_downloader,
        save_path=payload.save_path,
        status="pending",
        started_at=datetime.utcnow(),
    )
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return {"status": "created", "task": db_task.model_dump()}


# ============================================================
# 任务控制
# ============================================================
@router.post("/{task_id}/pause", status_code=204)
async def pause_download(task_id: int, session: Session = Depends(get_session)) -> None:
    task = session.get(DownloadTask, task_id)
    if not task:
        raise HTTPException(status_code=404)
    if not task.downloader_task_id:
        raise HTTPException(status_code=400, detail="no_downloader_task_id")
    p = downloader_factory.create_provider()
    if not p:
        raise HTTPException(status_code=500, detail="downloader_not_available")
    try:
        await p.pause(task.downloader_task_id)
    finally:
        await p.close()  # type: ignore[union-attr]


@router.post("/{task_id}/resume", status_code=204)
async def resume_download(task_id: int, session: Session = Depends(get_session)) -> None:
    task = session.get(DownloadTask, task_id)
    if not task:
        raise HTTPException(status_code=404)
    if not task.downloader_task_id:
        raise HTTPException(status_code=400, detail="no_downloader_task_id")
    p = downloader_factory.create_provider()
    if not p:
        raise HTTPException(status_code=500, detail="downloader_not_available")
    try:
        await p.resume(task.downloader_task_id)
    finally:
        await p.close()  # type: ignore[union-attr]


@router.delete("/{task_id}", status_code=204)
async def remove_download(
    task_id: int,
    delete_files: bool = False,
    session: Session = Depends(get_session),
) -> None:
    task = session.get(DownloadTask, task_id)
    if not task:
        raise HTTPException(status_code=404)
    # 先调下载器删除
    if task.downloader_task_id:
        p = downloader_factory.create_provider()
        if p:
            try:
                await p.remove(task.downloader_task_id, delete_files=delete_files)
            except Exception:  # noqa: BLE001
                pass  # 下载器侧失败也不阻止本地删除
            finally:
                await p.close()  # type: ignore[union-attr]
    session.delete(task)
    session.commit()
