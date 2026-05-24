"""下载状态同步任务。

定时(5s)向下载器查询所有进行中的任务,更新本地状态。
完成的任务触发入库流程(scan_service 重用)。
"""
import asyncio
import logging
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.db.session import engine
from app.models import DownloadTask, FileAsset, MediaFile, MediaItem, ScanPath
from app.providers.downloader import factory as downloader_factory
from app.providers.downloader.base import TorrentInfo
from app.services.filename_parser import parse_filename
from app.services.hashing import partial_hash

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5.0
_task: asyncio.Task | None = None


async def _sync_once() -> None:
    """跑一轮:从 qB 拉所有任务,合并到本地。"""
    if not downloader_factory.is_configured():
        return

    provider = downloader_factory.create_provider()
    if not provider:
        return

    try:
        try:
            torrents = await provider.list_all()
        except Exception as e:  # noqa: BLE001
            logger.debug("downloader list failed: %s", e)
            return
        torrents_by_hash: dict[str, TorrentInfo] = {t.info_hash.lower(): t for t in torrents if t.info_hash}

        with Session(engine) as session:
            db_tasks = session.exec(
                select(DownloadTask).where(
                    DownloadTask.status.in_(["pending", "downloading", "paused"])  # type: ignore[union-attr]
                )
            ).all()

            for db_t in db_tasks:
                if not db_t.info_hash:
                    continue
                t = torrents_by_hash.get(db_t.info_hash.lower())
                if not t:
                    # 任务从下载器消失了,标记错误(可能是手动删除)
                    db_t.status = "removed"
                    db_t.updated_at = datetime.utcnow()
                    session.add(db_t)
                    continue

                old_status = db_t.status
                db_t.status = t.status
                db_t.progress = t.progress
                db_t.download_speed = t.download_speed
                db_t.upload_speed = t.upload_speed
                db_t.eta_seconds = t.eta_seconds
                db_t.save_path = t.save_path or db_t.save_path
                db_t.updated_at = datetime.utcnow()
                if t.status == "completed" and old_status != "completed":
                    db_t.completed_at = datetime.utcnow()
                session.add(db_t)
            session.commit()

            # 处理新完成的任务
            done_tasks = session.exec(
                select(DownloadTask).where(
                    DownloadTask.status == "completed",
                    # 自定义字段标记是否处理过 - 这里复用 error_message 的 None 状态
                )
            ).all()
            # 我们用 progress=1.0 + completed_at 但没 file_asset 关联作为「未处理」的标志
            for db_t in done_tasks:
                # 看这个任务的 info_hash 是否已经在 file_asset 中(扫描或上次入库)
                already_imported = session.exec(
                    select(FileAsset)
                    .where(FileAsset.path.in_(_safe_paths(db_t.save_path or "")))  # type: ignore[union-attr]
                    .limit(1)
                ).first()
                if already_imported:
                    continue
                await _import_completed_task(provider, db_t)
    finally:
        await provider.close()  # type: ignore[union-attr]


def _safe_paths(p: str) -> list[str]:
    if not p:
        return [""]
    return [p]


async def _import_completed_task(provider, db_t: DownloadTask) -> None:
    """下载完成 → 把文件加入 file_asset + 关联 media_item。"""
    if not db_t.downloader_task_id:
        return
    try:
        files = await provider.get_files(db_t.downloader_task_id)
    except Exception as e:  # noqa: BLE001
        logger.debug("get_files failed: %s", e)
        return

    if not files:
        return

    from app.core.file_types import classify_file

    with Session(engine) as session:
        # 先确保有一个 scan_path 可关联(选 save_path 所在的扫描路径)
        scan_path = None
        if db_t.save_path:
            scan_paths = session.exec(select(ScanPath)).all()
            for sp in scan_paths:
                if db_t.save_path.startswith(sp.path):
                    scan_path = sp
                    break

        # 新建 media_item(若需要)
        title_norm = parse_filename(db_t.title).normalized_title
        media = None
        if title_norm:
            media = session.exec(
                select(MediaItem).where(MediaItem.normalized_title == title_norm)
            ).first()
        if not media:
            parsed = parse_filename(db_t.title)
            media = MediaItem(
                title=parsed.title or db_t.title,
                original_title=db_t.title,
                normalized_title=title_norm,
                release_date=str(parsed.year) if parsed.year else None,
            )
            session.add(media)
            session.flush()

        for file_path_str in files:
            p = Path(file_path_str)
            if not p.exists():
                continue
            ext = p.suffix.lower()
            ftype = classify_file(ext)
            if ftype is None:
                continue
            abs_path = str(p.resolve())
            existing = session.exec(select(FileAsset).where(FileAsset.path == abs_path)).first()
            if existing:
                continue
            stat = p.stat()
            try:
                ph = partial_hash(p)
            except OSError:
                ph = None
            asset = FileAsset(
                scan_path_id=scan_path.id if scan_path else None,
                path=abs_path,
                directory=str(p.resolve().parent),
                filename=p.name,
                extension=ext,
                size_bytes=stat.st_size,
                mtime=datetime.utcfromtimestamp(stat.st_mtime),
                partial_hash=ph,
                file_type=ftype,
            )
            session.add(asset)
            session.flush()
            if ftype == "video":
                mf = MediaFile(
                    media_item_id=media.id,  # type: ignore[arg-type]
                    file_asset_id=asset.id,  # type: ignore[arg-type]
                    container=ext.lstrip("."),
                )
                session.add(mf)
        session.commit()
        logger.info(
            "Imported %d files for download task #%s into media #%s",
            len(files),
            db_t.id,
            media.id,
        )


async def _loop() -> None:
    logger.info("download status sync started (interval=%ss)", POLL_INTERVAL)
    while True:
        try:
            await _sync_once()
        except asyncio.CancelledError:
            break
        except Exception:  # noqa: BLE001
            logger.exception("download sync error")
        await asyncio.sleep(POLL_INTERVAL)


def start_worker() -> None:
    global _task
    if _task and not _task.done():
        return
    _task = asyncio.create_task(_loop(), name="download-sync")


async def stop_worker() -> None:
    global _task
    if _task and not _task.done():
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
    _task = None
