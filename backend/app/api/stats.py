"""统计接口,供 Dashboard 使用。"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from app.db.session import get_session
from app.models import (
    Author,
    DownloadTask,
    FileAsset,
    MediaFile,
    MediaItem,
    PlaybackHistory,
    ScanJob,
    Tag,
)
from app.providers.downloader import factory as dl_factory
from app.providers.player import factory as jf_factory

router = APIRouter()


@router.get("")
def get_stats(session: Session = Depends(get_session)) -> dict:
    """返回 Dashboard 需要的所有统计数据。"""

    # 资源/文件计数
    media_count = session.exec(select(func.count(MediaItem.id))).one()  # type: ignore[arg-type]
    file_count = session.exec(select(func.count(FileAsset.id))).one()  # type: ignore[arg-type]
    video_count = session.exec(
        select(func.count(FileAsset.id)).where(FileAsset.file_type == "video")  # type: ignore[arg-type]
    ).one()
    missing_count = session.exec(
        select(func.count(FileAsset.id)).where(FileAsset.missing == True)  # type: ignore[arg-type]  # noqa: E712
    ).one()

    # 总大小
    total_size = (
        session.exec(
            select(func.coalesce(func.sum(FileAsset.size_bytes), 0)).where(  # type: ignore[arg-type]
                FileAsset.missing == False  # noqa: E712
            )
        ).one()
        or 0
    )

    # 收藏 / 已看 / 未看
    favorite_count = session.exec(
        select(func.count(MediaItem.id)).where(MediaItem.favorite == True)  # type: ignore[arg-type]  # noqa: E712
    ).one()
    watched_count = session.exec(
        select(func.count(MediaItem.id)).where(MediaItem.watch_status == "watched")  # type: ignore[arg-type]
    ).one()
    unwatched_count = session.exec(
        select(func.count(MediaItem.id)).where(MediaItem.watch_status == "unwatched")  # type: ignore[arg-type]
    ).one()

    # 元数据计数
    author_count = session.exec(select(func.count(Author.id))).one()  # type: ignore[arg-type]
    tag_count = session.exec(select(func.count(Tag.id))).one()  # type: ignore[arg-type]

    # 下载任务
    downloading_count = session.exec(
        select(func.count(DownloadTask.id)).where(  # type: ignore[arg-type]
            DownloadTask.status.in_(["downloading", "pending"])  # type: ignore[union-attr]
        )
    ).one()
    completed_dl_count = session.exec(
        select(func.count(DownloadTask.id)).where(DownloadTask.status == "completed")  # type: ignore[arg-type]
    ).one()

    # 最近扫描
    last_scan = session.exec(
        select(ScanJob).order_by(ScanJob.id.desc()).limit(1)  # type: ignore[union-attr]
    ).first()

    # 最近 7 天入库
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_added = session.exec(
        select(func.count(MediaItem.id)).where(MediaItem.created_at >= seven_days_ago)  # type: ignore[arg-type]
    ).one()

    # 最近播放
    recent_played = session.exec(
        select(PlaybackHistory)
        .order_by(PlaybackHistory.id.desc())  # type: ignore[union-attr]
        .limit(5)
    ).all()

    return {
        "media_count": media_count,
        "file_count": file_count,
        "video_count": video_count,
        "missing_count": missing_count,
        "total_size_bytes": total_size,
        "favorite_count": favorite_count,
        "watched_count": watched_count,
        "unwatched_count": unwatched_count,
        "author_count": author_count,
        "tag_count": tag_count,
        "downloading_count": downloading_count,
        "completed_dl_count": completed_dl_count,
        "recent_added": recent_added,
        "recent_played_count": len(recent_played),
        "last_scan": (
            {
                "id": last_scan.id,
                "status": last_scan.status,
                "scanned_files": last_scan.scanned_files,
                "new_files": last_scan.new_files,
                "started_at": last_scan.started_at.isoformat() + "Z" if last_scan.started_at else None,
                "finished_at": last_scan.finished_at.isoformat() + "Z" if last_scan.finished_at else None,
            }
            if last_scan
            else None
        ),
        "qbittorrent_configured": dl_factory.is_configured(),
        "jellyfin_configured": jf_factory.is_configured(),
    }


@router.get("/recent-media")
def recent_media(
    limit: int = 12, session: Session = Depends(get_session)
) -> list[dict]:
    """最近入库的资源列表。"""
    items = session.exec(
        select(MediaItem).order_by(MediaItem.created_at.desc()).limit(limit)  # type: ignore[union-attr]
    ).all()

    # 取每个 media 的文件数
    counts: dict[int, int] = {}
    if items:
        rows = session.exec(
            select(MediaFile.media_item_id, func.count(MediaFile.id))  # type: ignore[arg-type]
            .where(MediaFile.media_item_id.in_([i.id for i in items]))  # type: ignore[union-attr]
            .group_by(MediaFile.media_item_id)
        ).all()
        counts = {r[0]: r[1] for r in rows}

    return [
        {
            "id": i.id,
            "title": i.title,
            "cover_path": i.cover_path,
            "file_count": counts.get(i.id, 0),  # type: ignore[arg-type]
            "favorite": i.favorite,
            "watch_status": i.watch_status,
            "created_at": i.created_at.isoformat() + "Z",
        }
        for i in items
    ]
