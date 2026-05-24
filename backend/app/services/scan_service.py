"""文件扫描服务。

核心流程:
1. 遍历 scan_path 目录,过滤已知扩展名
2. 对每个文件计算 stat + partial_hash
3. 路径已存在则更新,否则插入 file_asset
4. 视频文件自动创建 media_item 并建立 media_file 关联
5. 异步 ffprobe (可选)
6. 写 scan_log,更新 scan_job 进度

设计考虑:
- 单消费者(asyncio.Queue),避免 SQLite 写锁竞争
- 每文件一次小事务,失败不影响后续
- partial_hash 可能比 stat 慢(IO),但比 ffprobe 快很多
"""
import asyncio
import logging
import os
from datetime import datetime
from pathlib import Path

from sqlmodel import Session, select

from app.core.file_types import VIDEO_EXTENSIONS, classify_file
from app.db.session import engine
from app.models import FileAsset, MediaFile, MediaItem, ScanJob, ScanLog, ScanPath
from app.services import ffprobe_service
from app.services.filename_parser import parse_filename
from app.services.hashing import partial_hash

logger = logging.getLogger(__name__)


# ============================================================
# 工具
# ============================================================
def _walk_files(root: Path, recursive: bool):
    """生成 (file_path, stat) 元组,过滤已知扩展名。"""
    if not root.exists():
        return
    if recursive:
        for dirpath, _dirs, files in os.walk(root, followlinks=False):
            for name in files:
                yield Path(dirpath) / name
    else:
        for entry in root.iterdir():
            if entry.is_file():
                yield entry


def _log(session: Session, job_id: int, message: str, file_path: str | None = None, level: str = "info") -> None:
    session.add(ScanLog(scan_job_id=job_id, level=level, message=message, file_path=file_path))


# ============================================================
# 单文件处理(同步,因为 SQLite 写)
# ============================================================
def _upsert_file_asset(
    session: Session,
    job_id: int,
    scan_path: ScanPath,
    file_path: Path,
) -> tuple[FileAsset, bool]:
    """处理单个文件,返回 (asset, is_new)。"""
    abs_path = str(file_path.resolve())
    stat = file_path.stat()
    ext = file_path.suffix.lower()
    file_type = classify_file(ext)

    if file_type is None:
        # 不在白名单,跳过(不入库)
        return None, False  # type: ignore[return-value]

    existing = session.exec(select(FileAsset).where(FileAsset.path == abs_path)).first()

    if existing:
        # 已有记录,看 mtime / size 是否变化
        new_mtime = datetime.utcfromtimestamp(stat.st_mtime)
        if (
            existing.size_bytes == stat.st_size
            and existing.mtime
            and abs((existing.mtime - new_mtime).total_seconds()) < 1
        ):
            existing.missing = False
            existing.scan_status = "active"
            session.add(existing)
            return existing, False
        # 文件被改过,重算 hash
        existing.size_bytes = stat.st_size
        existing.mtime = new_mtime
        try:
            existing.partial_hash = partial_hash(file_path)
        except OSError as e:
            _log(session, job_id, f"hash failed: {e}", abs_path, "warn")
        existing.missing = False
        existing.scan_status = "active"
        existing.updated_at = datetime.utcnow()
        session.add(existing)
        return existing, False

    # 新文件
    try:
        ph = partial_hash(file_path)
    except OSError as e:
        _log(session, job_id, f"hash failed: {e}", abs_path, "warn")
        ph = None

    asset = FileAsset(
        scan_path_id=scan_path.id,
        path=abs_path,
        directory=str(file_path.resolve().parent),
        filename=file_path.name,
        extension=ext,
        size_bytes=stat.st_size,
        mtime=datetime.utcfromtimestamp(stat.st_mtime),
        partial_hash=ph,
        file_type=file_type,
        scan_status="active",
        missing=False,
    )
    session.add(asset)
    session.flush()  # 拿 id
    return asset, True


def _ensure_media_item_for_video(session: Session, asset: FileAsset, scan_path: ScanPath) -> MediaItem | None:
    """为视频文件确保有对应的 media_item,返回新建或已有的。"""
    if asset.file_type != "video":
        return None

    # 已经关联过?
    existing_link = session.exec(
        select(MediaFile).where(MediaFile.file_asset_id == asset.id)
    ).first()
    if existing_link:
        return session.get(MediaItem, existing_link.media_item_id)

    # 解析文件名
    name_no_ext = Path(asset.filename).stem
    parsed = parse_filename(name_no_ext)

    # 用 normalized_title 找现有 media_item(后续作为去重的弱信号)
    media = None
    if parsed.normalized_title:
        media = session.exec(
            select(MediaItem).where(MediaItem.normalized_title == parsed.normalized_title)
        ).first()

    if not media:
        media = MediaItem(
            title=parsed.title,
            original_title=parsed.raw,
            normalized_title=parsed.normalized_title,
            release_date=str(parsed.year) if parsed.year else None,
        )
        session.add(media)
        session.flush()

    # 创建 media_file 关联
    mf = MediaFile(
        media_item_id=media.id,  # type: ignore[arg-type]
        file_asset_id=asset.id,  # type: ignore[arg-type]
        quality=parsed.quality,
        container=asset.extension.lstrip(".") if asset.extension else None,
        is_primary=False,  # 后续可由用户标记
    )
    session.add(mf)
    return media


# ============================================================
# 扫描任务执行(异步,但内部 SQLite 操作是同步的)
# ============================================================
async def run_scan_job(scan_path_id: int) -> None:
    """执行一次扫描任务,创建 ScanJob 并跑完。"""
    # Phase 1: 准备 - 创建 job, 记录路径配置
    with Session(engine) as session:
        scan_path = session.get(ScanPath, scan_path_id)
        if not scan_path:
            logger.error("scan_path_id=%s not found", scan_path_id)
            return

        # 提取需要的字段值,避免 detached 后访问
        sp_path = scan_path.path
        sp_recursive = scan_path.recursive

        job = ScanJob(scan_path_id=scan_path_id, status="running", started_at=datetime.utcnow())
        session.add(job)
        session.commit()
        session.refresh(job)
        job_id: int = job.id  # type: ignore[assignment]

    root = Path(sp_path)
    if not root.exists():
        with Session(engine) as session:
            j = session.get(ScanJob, job_id)
            j.status = "failed"  # type: ignore[union-attr]
            j.error_message = f"path not exists: {root}"  # type: ignore[union-attr]
            j.finished_at = datetime.utcnow()  # type: ignore[union-attr]
            session.add(j)
            _log(session, job_id, f"path not exists: {root}", level="error")
            session.commit()
        return

    # Phase 2: 列文件
    files: list[Path] = []
    for f in _walk_files(root, sp_recursive):
        ext = f.suffix.lower()
        if classify_file(ext) is not None:
            files.append(f)

    with Session(engine) as session:
        j = session.get(ScanJob, job_id)
        j.total_files = len(files)  # type: ignore[union-attr]
        session.add(j)
        session.commit()

    logger.info("Scan job %d: %d candidate files in %s", job_id, len(files), root)

    # Phase 3: 逐文件处理
    new_count = updated_count = 0
    probe_targets: list[tuple[int, str]] = []  # (file_asset_id, abs_path)

    for idx, f in enumerate(files):
        try:
            with Session(engine) as session:
                # 重新 attach scan_path
                sp = session.get(ScanPath, scan_path_id)
                asset, is_new = _upsert_file_asset(session, job_id, sp, f)  # type: ignore[arg-type]
                if asset is None:
                    continue
                _ensure_media_item_for_video(session, asset, sp)  # type: ignore[arg-type]
                session.commit()

                if asset.file_type == "video" and is_new:
                    probe_targets.append((asset.id, asset.path))  # type: ignore[arg-type]

                if is_new:
                    new_count += 1
                else:
                    updated_count += 1
        except Exception as e:  # noqa: BLE001
            logger.exception("scan error at %s", f)
            with Session(engine) as session:
                _log(session, job_id, f"error: {e}", str(f), "error")
                session.commit()

        # 每 20 个文件刷一次进度
        if (idx + 1) % 20 == 0 or idx + 1 == len(files):
            with Session(engine) as session:
                j = session.get(ScanJob, job_id)
                j.scanned_files = idx + 1  # type: ignore[union-attr]
                j.new_files = new_count  # type: ignore[union-attr]
                j.updated_files = updated_count  # type: ignore[union-attr]
                session.add(j)
                session.commit()

    # Phase 4: 标记失踪文件
    with Session(engine) as session:
        all_assets = session.exec(
            select(FileAsset).where(FileAsset.scan_path_id == scan_path_id)
        ).all()
        existing_paths = {str(p.resolve()) for p in files}
        missing = 0
        for a in all_assets:
            if a.path not in existing_paths and not a.missing:
                a.missing = True
                a.scan_status = "missing"
                session.add(a)
                missing += 1
        if missing:
            _log(session, job_id, f"marked {missing} files as missing")
        session.commit()

    # Phase 5: ffprobe 异步探测(并发上限 4,避免吃满 IO)
    if ffprobe_service.is_available() and probe_targets:
        sem = asyncio.Semaphore(4)

        async def _probe_one(asset_id: int, p: str) -> None:
            async with sem:
                result = await ffprobe_service.probe(p)
                if not result:
                    return
                with Session(engine) as session:
                    asset = session.get(FileAsset, asset_id)
                    if not asset:
                        return
                    asset.media_probe_json = result.raw_json
                    session.add(asset)

                    mf = session.exec(
                        select(MediaFile).where(MediaFile.file_asset_id == asset_id)
                    ).first()
                    if mf:
                        mf.duration_seconds = result.duration_seconds
                        mf.width = result.width
                        mf.height = result.height
                        mf.video_codec = result.video_codec
                        mf.audio_codec = result.audio_codec
                        if not mf.container and result.container:
                            mf.container = result.container
                        session.add(mf)
                    session.commit()

        await asyncio.gather(*(_probe_one(aid, p) for aid, p in probe_targets))

    # Phase 6: 收尾
    with Session(engine) as session:
        j = session.get(ScanJob, job_id)
        j.status = "success"  # type: ignore[union-attr]
        j.scanned_files = len(files)  # type: ignore[union-attr]
        j.new_files = new_count  # type: ignore[union-attr]
        j.updated_files = updated_count  # type: ignore[union-attr]
        j.missing_files = missing if "missing" in locals() else 0  # type: ignore[union-attr]
        j.finished_at = datetime.utcnow()  # type: ignore[union-attr]
        session.add(j)

        sp = session.get(ScanPath, scan_path_id)
        if sp:
            sp.last_scan_at = datetime.utcnow()
            session.add(sp)

        _log(session, job_id, f"scan complete: new={new_count} updated={updated_count}")
        session.commit()

    # Phase 7: 同步 FTS 索引
    from app.services import search_service

    with Session(engine) as session:
        media_ids = [m.id for m in session.exec(select(MediaItem)).all() if m.id]
        for mid in media_ids:
            search_service.sync_one(session, mid)
        session.commit()

    logger.info("Scan job %d done: new=%d updated=%d", job_id, new_count, updated_count)
