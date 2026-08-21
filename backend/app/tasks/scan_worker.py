"""扫描任务后台 worker。

设计:
- 全局单消费者 asyncio.Queue,串行执行扫描任务
- 串行可避免 SQLite 写锁竞争
- main.py lifespan 启动时拉起,关闭时取消
- _active_path_ids 记录"已入队但还没跑完"的 scan_path_id,用于在入队瞬间就能
  拒绝重复触发(比查数据库里的 ScanJob 状态更可靠:入队和 ScanJob 记录创建
  之间有一个时间窗口,单纯查库会有竞态,这里在内存里维护集合从入队那一刻起
  就能感知到"已经有一个在排队/运行了")
"""
import asyncio
import logging

from app.services.scan_service import run_scan_job

logger = logging.getLogger(__name__)

_queue: asyncio.Queue[int] | None = None
_task: asyncio.Task | None = None
_active_path_ids: set[int] = set()


def get_queue() -> asyncio.Queue[int]:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


def is_active(scan_path_id: int) -> bool:
    """该路径是否已有任务在排队或运行中。"""
    return scan_path_id in _active_path_ids


async def _worker() -> None:
    queue = get_queue()
    logger.info("scan worker started")
    while True:
        try:
            scan_path_id = await queue.get()
        except asyncio.CancelledError:
            break
        try:
            await run_scan_job(scan_path_id)
        except Exception:  # noqa: BLE001
            logger.exception("scan worker error for path_id=%s", scan_path_id)
        finally:
            _active_path_ids.discard(scan_path_id)
            queue.task_done()


def start_worker() -> None:
    global _task
    if _task and not _task.done():
        return
    _cleanup_stale_jobs()
    _task = asyncio.create_task(_worker(), name="scan-worker")


def _cleanup_stale_jobs() -> None:
    """进程启动时,把数据库里残留的 pending/running/enriching/dedup 状态任务标记为失败。

    这些记录必然是上次进程异常退出(容器重启、崩溃)时遗留的僵死状态——
    本次是全新进程,内存里的活跃路径集合是空的,不可能真的还有任务在跑。
    不清理的话,这些路径会永久被误认为"仍在扫描中",导致用户再也无法触发新的扫描。
    """
    from datetime import datetime

    from sqlmodel import Session, select

    from app.db.session import engine
    from app.models import ScanJob

    with Session(engine) as session:
        stale = session.exec(
            select(ScanJob).where(
                ScanJob.status.in_(["pending", "running", "enriching", "dedup"])  # type: ignore[union-attr]
            )
        ).all()
        if not stale:
            return
        for j in stale:
            j.status = "failed"
            j.phase = "done"
            j.error_message = "interrupted_by_restart"
            j.finished_at = datetime.utcnow()
            session.add(j)
        session.commit()
        logger.warning("Marked %d stale scan job(s) as failed on startup", len(stale))


async def stop_worker() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
    _active_path_ids.clear()


async def enqueue(scan_path_id: int) -> bool:
    """入队一次扫描请求。

    返回 False 表示该路径已有任务在排队/运行,本次请求被拒绝、未入队。
    """
    if scan_path_id in _active_path_ids:
        return False
    _active_path_ids.add(scan_path_id)
    await get_queue().put(scan_path_id)
    return True
