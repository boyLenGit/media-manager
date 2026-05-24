"""扫描任务后台 worker。

设计:
- 全局单消费者 asyncio.Queue,串行执行扫描任务
- 串行可避免 SQLite 写锁竞争
- main.py lifespan 启动时拉起,关闭时取消
"""
import asyncio
import logging

from app.services.scan_service import run_scan_job

logger = logging.getLogger(__name__)

_queue: asyncio.Queue[int] | None = None
_task: asyncio.Task | None = None


def get_queue() -> asyncio.Queue[int]:
    global _queue
    if _queue is None:
        _queue = asyncio.Queue()
    return _queue


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
            queue.task_done()


def start_worker() -> None:
    global _task
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_worker(), name="scan-worker")


async def stop_worker() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None


async def enqueue(scan_path_id: int) -> None:
    await get_queue().put(scan_path_id)
