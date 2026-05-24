"""扫描相关接口。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.db.session import get_session
from app.models import ScanJob, ScanLog, ScanPath
from app.tasks import scan_worker

router = APIRouter()


# ============================================================
# Schemas
# ============================================================
class ScanPathIn(BaseModel):
    path: str
    name: str | None = None
    enabled: bool = True
    recursive: bool = True
    default_media_type: str | None = None
    default_tags: str | None = None


class ScanPathOut(ScanPathIn):
    id: int
    last_scan_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


# ============================================================
# 扫描路径 CRUD
# ============================================================
@router.get("/paths")
def list_scan_paths(session: Session = Depends(get_session)) -> list[ScanPath]:
    return session.exec(select(ScanPath).order_by(ScanPath.id)).all()  # type: ignore[union-attr]


@router.post("/paths", status_code=201)
def create_scan_path(
    payload: ScanPathIn, session: Session = Depends(get_session)
) -> ScanPath:
    if session.exec(select(ScanPath).where(ScanPath.path == payload.path)).first():
        raise HTTPException(status_code=409, detail="path_already_exists")
    obj = ScanPath(**payload.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.patch("/paths/{path_id}")
def update_scan_path(
    path_id: int, payload: ScanPathIn, session: Session = Depends(get_session)
) -> ScanPath:
    obj = session.get(ScanPath, path_id)
    if not obj:
        raise HTTPException(status_code=404)
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.delete("/paths/{path_id}", status_code=204)
def delete_scan_path(path_id: int, session: Session = Depends(get_session)) -> None:
    obj = session.get(ScanPath, path_id)
    if not obj:
        raise HTTPException(status_code=404)
    session.delete(obj)
    session.commit()


# ============================================================
# 扫描任务
# ============================================================
@router.post("/paths/{path_id}/scan", status_code=202)
async def trigger_scan(path_id: int, session: Session = Depends(get_session)) -> dict:
    """触发一次扫描,任务异步执行。"""
    sp = session.get(ScanPath, path_id)
    if not sp:
        raise HTTPException(status_code=404, detail="scan_path_not_found")
    if not sp.enabled:
        raise HTTPException(status_code=400, detail="scan_path_disabled")
    await scan_worker.enqueue(path_id)
    return {"status": "queued", "scan_path_id": path_id}


@router.get("/jobs")
def list_jobs(
    limit: int = 20, session: Session = Depends(get_session)
) -> list[ScanJob]:
    return session.exec(
        select(ScanJob).order_by(ScanJob.id.desc()).limit(limit)  # type: ignore[union-attr]
    ).all()


@router.get("/jobs/{job_id}")
def get_job(job_id: int, session: Session = Depends(get_session)) -> ScanJob:
    j = session.get(ScanJob, job_id)
    if not j:
        raise HTTPException(status_code=404)
    return j


@router.get("/jobs/{job_id}/logs")
def get_job_logs(
    job_id: int, limit: int = 200, session: Session = Depends(get_session)
) -> list[ScanLog]:
    return session.exec(
        select(ScanLog)
        .where(ScanLog.scan_job_id == job_id)
        .order_by(ScanLog.id.desc())  # type: ignore[union-attr]
        .limit(limit)
    ).all()
