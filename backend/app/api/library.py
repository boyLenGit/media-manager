"""资源库 API。"""
import logging
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.deps import require_admin
from app.db.session import get_session
from app.models import (
    Author,
    FileAsset,
    MediaFile,
    MediaItem,
    MediaTag,
    MediaType,
    Tag,
    User,
)
from app.services import audit_service, search_service, thumbnail_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Schemas
# ============================================================
class MediaItemBrief(BaseModel):
    id: int
    title: str
    original_title: str | None = None
    normalized_title: str | None = None
    media_type_id: int | None = None
    media_type_name: str | None = None
    author_id: int | None = None
    author_name: str | None = None
    release_date: str | None = None
    cover_path: str | None = None
    rating: float | None = None
    favorite: bool
    watch_status: str
    file_count: int = 0
    tags: list[dict] = []
    created_at: datetime
    updated_at: datetime


class MediaFileDetail(BaseModel):
    id: int
    file_asset_id: int
    path: str
    filename: str
    extension: str | None = None
    size_bytes: int | None = None
    quality: str | None = None
    container: str | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    is_primary: bool
    missing: bool


class MediaItemDetail(MediaItemBrief):
    description: str | None = None
    source_url: str | None = None
    remark: str | None = None
    files: list[MediaFileDetail] = []


class UpdateMediaIn(BaseModel):
    title: str | None = None
    media_type_id: int | None = None
    author_id: int | None = None
    favorite: bool | None = None
    watch_status: str | None = None
    rating: float | None = None
    description: str | None = None
    remark: str | None = None
    tag_ids: list[int] | None = None


class BatchTagIn(BaseModel):
    media_ids: list[int]
    add_tag_ids: list[int] = []
    remove_tag_ids: list[int] = []


class BatchUpdateIn(BaseModel):
    media_ids: list[int]
    media_type_id: int | None = None
    author_id: int | None = None
    favorite: bool | None = None
    watch_status: str | None = None


# ============================================================
# 辅助
# ============================================================
def _build_brief(
    session: Session,
    item: MediaItem,
    author_map: dict[int, str],
    type_map: dict[int, str],
    file_count_map: dict[int, int],
) -> MediaItemBrief:
    tag_rows = session.exec(
        select(Tag.id, Tag.name, Tag.color, Tag.group_name)  # type: ignore[arg-type]
        .join(MediaTag, MediaTag.tag_id == Tag.id)  # type: ignore[arg-type]
        .where(MediaTag.media_item_id == item.id)
    ).all()
    tags = [{"id": r[0], "name": r[1], "color": r[2], "group": r[3]} for r in tag_rows]

    return MediaItemBrief(
        id=item.id,  # type: ignore[arg-type]
        title=item.title,
        original_title=item.original_title,
        normalized_title=item.normalized_title,
        media_type_id=item.media_type_id,
        media_type_name=type_map.get(item.media_type_id) if item.media_type_id else None,
        author_id=item.author_id,
        author_name=author_map.get(item.author_id) if item.author_id else None,
        release_date=item.release_date,
        cover_path=item.cover_path,
        rating=item.rating,
        favorite=item.favorite,
        watch_status=item.watch_status,
        file_count=file_count_map.get(item.id, 0),  # type: ignore[arg-type]
        tags=tags,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


# ============================================================
# 列表
# ============================================================
@router.get("")
def list_media(
    q: str | None = Query(default=None, description="标题模糊搜索"),
    media_type_id: int | None = None,
    author_id: int | None = None,
    favorite: bool | None = None,
    watch_status: str | None = None,
    tag_id: int | None = None,
    sort_by: str = Query(default="updated_at", pattern="^(updated_at|created_at|title|rating)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: Session = Depends(get_session),
) -> dict:
    stmt = select(MediaItem)
    if q:
        stmt = stmt.where(MediaItem.title.contains(q))  # type: ignore[union-attr]
    if media_type_id is not None:
        stmt = stmt.where(MediaItem.media_type_id == media_type_id)
    if author_id is not None:
        stmt = stmt.where(MediaItem.author_id == author_id)
    if favorite is not None:
        stmt = stmt.where(MediaItem.favorite == favorite)
    if watch_status:
        stmt = stmt.where(MediaItem.watch_status == watch_status)
    if tag_id is not None:
        stmt = stmt.join(MediaTag, MediaTag.media_item_id == MediaItem.id).where(  # type: ignore[arg-type]
            MediaTag.tag_id == tag_id
        )

    # 排序
    sort_col = getattr(MediaItem, sort_by)
    stmt = stmt.order_by(sort_col.desc() if order == "desc" else sort_col.asc())

    # 分页前先算 total
    total = session.exec(
        select(func.count()).select_from(stmt.subquery())  # type: ignore[arg-type]
    ).one()

    items = session.exec(stmt.offset(offset).limit(limit)).all()

    # 批量取作者/类型/文件计数,避免 N+1
    author_ids = {i.author_id for i in items if i.author_id}
    type_ids = {i.media_type_id for i in items if i.media_type_id}
    item_ids = [i.id for i in items if i.id]

    author_map: dict[int, str] = {}
    if author_ids:
        rows = session.exec(select(Author.id, Author.name).where(Author.id.in_(author_ids))).all()  # type: ignore[arg-type]
        author_map = {r[0]: r[1] for r in rows}

    type_map: dict[int, str] = {}
    if type_ids:
        rows = session.exec(
            select(MediaType.id, MediaType.name).where(MediaType.id.in_(type_ids))  # type: ignore[arg-type]
        ).all()
        type_map = {r[0]: r[1] for r in rows}

    file_count_map: dict[int, int] = {}
    if item_ids:
        rows = session.exec(
            select(MediaFile.media_item_id, func.count(MediaFile.id))  # type: ignore[arg-type]
            .where(MediaFile.media_item_id.in_(item_ids))  # type: ignore[union-attr]
            .group_by(MediaFile.media_item_id)
        ).all()
        file_count_map = {r[0]: r[1] for r in rows}

    return {
        "items": [_build_brief(session, i, author_map, type_map, file_count_map) for i in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


# ============================================================
# 详情
# ============================================================
@router.get("/{media_id}")
def get_media(media_id: int, session: Session = Depends(get_session)) -> MediaItemDetail:
    item = session.get(MediaItem, media_id)
    if not item:
        raise HTTPException(status_code=404, detail="media_not_found")

    author_map: dict[int, str] = {}
    if item.author_id:
        a = session.get(Author, item.author_id)
        if a:
            author_map[a.id] = a.name  # type: ignore[index]
    type_map: dict[int, str] = {}
    if item.media_type_id:
        t = session.get(MediaType, item.media_type_id)
        if t:
            type_map[t.id] = t.name  # type: ignore[index]

    # 文件列表
    rows = session.exec(
        select(MediaFile, FileAsset)
        .join(FileAsset, FileAsset.id == MediaFile.file_asset_id)  # type: ignore[arg-type]
        .where(MediaFile.media_item_id == media_id)
        .order_by(MediaFile.is_primary.desc(), MediaFile.id)  # type: ignore[union-attr]
    ).all()

    files = [
        MediaFileDetail(
            id=mf.id,  # type: ignore[arg-type]
            file_asset_id=fa.id,  # type: ignore[arg-type]
            path=fa.path,
            filename=fa.filename,
            extension=fa.extension,
            size_bytes=fa.size_bytes,
            quality=mf.quality,
            container=mf.container,
            video_codec=mf.video_codec,
            audio_codec=mf.audio_codec,
            duration_seconds=mf.duration_seconds,
            width=mf.width,
            height=mf.height,
            is_primary=mf.is_primary,
            missing=fa.missing,
        )
        for mf, fa in rows
    ]

    brief = _build_brief(session, item, author_map, type_map, {item.id: len(files)})  # type: ignore[arg-type]
    return MediaItemDetail(
        **brief.model_dump(),
        description=item.description,
        source_url=item.source_url,
        remark=item.remark,
        files=files,
    )


# ============================================================
# 更新
# ============================================================
@router.patch("/{media_id}")
def update_media(
    media_id: int,
    payload: UpdateMediaIn,
    session: Session = Depends(get_session),
) -> MediaItemDetail:
    item = session.get(MediaItem, media_id)
    if not item:
        raise HTTPException(status_code=404, detail="media_not_found")

    data = payload.model_dump(exclude_unset=True)
    tag_ids = data.pop("tag_ids", None)

    for k, v in data.items():
        setattr(item, k, v)
    item.updated_at = datetime.utcnow()
    session.add(item)

    if tag_ids is not None:
        # 重置标签关联
        existing = session.exec(select(MediaTag).where(MediaTag.media_item_id == media_id)).all()
        for e in existing:
            session.delete(e)
        for tid in tag_ids:
            session.add(MediaTag(media_item_id=media_id, tag_id=tid))

    # FTS 同步
    search_service.sync_one(session, media_id)
    session.commit()
    return get_media(media_id, session)


# ============================================================
# 批量操作
# ============================================================
@router.post("/batch-tag")
def batch_tag(
    payload: BatchTagIn, session: Session = Depends(get_session)
) -> dict:
    """批量为多个 media 增/删标签。"""
    if not payload.media_ids:
        return {"affected": 0}

    affected = 0
    for mid in payload.media_ids:
        item = session.get(MediaItem, mid)
        if not item:
            continue
        # 添加(忽略已存在)
        for tid in payload.add_tag_ids:
            existing = session.exec(
                select(MediaTag).where(
                    MediaTag.media_item_id == mid, MediaTag.tag_id == tid
                )
            ).first()
            if not existing:
                session.add(MediaTag(media_item_id=mid, tag_id=tid))
        # 移除
        for tid in payload.remove_tag_ids:
            existing = session.exec(
                select(MediaTag).where(
                    MediaTag.media_item_id == mid, MediaTag.tag_id == tid
                )
            ).first()
            if existing:
                session.delete(existing)
        item.updated_at = datetime.utcnow()
        session.add(item)
        affected += 1

    session.commit()
    # FTS 同步(批量,在 commit 后单独 session 处理)
    for mid in payload.media_ids:
        search_service.sync_one(session, mid)
    session.commit()
    return {"affected": affected}


@router.post("/batch-update")
def batch_update(
    payload: BatchUpdateIn, session: Session = Depends(get_session)
) -> dict:
    """批量更新多个 media 的字段。"""
    if not payload.media_ids:
        return {"affected": 0}

    data = payload.model_dump(exclude={"media_ids"}, exclude_unset=True)
    if not data:
        return {"affected": 0}

    affected = 0
    for mid in payload.media_ids:
        item = session.get(MediaItem, mid)
        if not item:
            continue
        for k, v in data.items():
            setattr(item, k, v)
        item.updated_at = datetime.utcnow()
        session.add(item)
        affected += 1
    session.commit()
    for mid in payload.media_ids:
        search_service.sync_one(session, mid)
    session.commit()
    return {"affected": affected}


# ============================================================
# 删除资源
# ============================================================
class DeleteMediaIn(BaseModel):
    delete_files: bool = False  # 是否同时删除磁盘上的视频文件


class DeleteMediaResult(BaseModel):
    media_id: int
    deleted_files: list[str] = []  # 成功删除的磁盘文件
    failed_files: list[dict] = []  # [{"path": ..., "reason": "permission_denied" | ...}]
    db_removed: bool


@router.delete("/{media_id}")
def delete_media(
    media_id: int,
    delete_files: bool = Query(default=False, description="是否同时删除磁盘文件"),
    request: Request = None,  # type: ignore[assignment]
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> DeleteMediaResult:
    """删除一个 media_item。

    - delete_files=False (默认): 仅清理 DB(media_item / media_file / media_tag / 缩略图),
      file_asset 保留(但其 media_file 关联会被删除,下次扫描会重新建立或保持孤儿状态)
    - delete_files=True: 尝试删除磁盘上的真实视频文件;无权限时返回 failed_files,
      DB 仍然清理(避免 UI 上 "明明删了还在")
    """
    item = session.get(MediaItem, media_id)
    if not item:
        raise HTTPException(status_code=404, detail="media_not_found")

    # 收集所有关联的物理文件路径
    rows = session.exec(
        select(FileAsset)
        .join(MediaFile, MediaFile.file_asset_id == FileAsset.id)  # type: ignore[arg-type]
        .where(MediaFile.media_item_id == media_id)
    ).all()
    paths = [(fa.id, fa.path) for fa in rows]

    deleted_files: list[str] = []
    failed_files: list[dict] = []

    # 1. 可选: 删磁盘文件
    if delete_files:
        for fa_id, p in paths:
            try:
                if os.path.exists(p):
                    os.remove(p)
                    deleted_files.append(p)
                else:
                    # 文件本来就不在,不算失败
                    deleted_files.append(p)
            except PermissionError:
                failed_files.append({"path": p, "reason": "permission_denied"})
            except OSError as e:
                failed_files.append({"path": p, "reason": f"os_error: {e}"})

    # 2. 删 DB 关联
    # media_tag, media_file 都靠 ON DELETE CASCADE,但保险起见显式删
    media_tags = session.exec(select(MediaTag).where(MediaTag.media_item_id == media_id)).all()
    for mt in media_tags:
        session.delete(mt)
    media_files = session.exec(select(MediaFile).where(MediaFile.media_item_id == media_id)).all()
    fa_ids_to_check = {mf.file_asset_id for mf in media_files}
    for mf in media_files:
        session.delete(mf)

    # 3. 如果删了文件,把对应 file_asset 也清掉(否则会作为孤儿一直存在)
    if delete_files:
        for fa_id in fa_ids_to_check:
            fa = session.get(FileAsset, fa_id)
            if fa:
                session.delete(fa)

    # 4. 清缩略图文件
    try:
        tp = thumbnail_service.get_thumbnail_path(media_id)
        if tp.exists():
            tp.unlink()
    except Exception as e:  # noqa: BLE001
        logger.warning("clean thumbnail failed for %d: %s", media_id, e)

    # 5. FTS 索引清理 + 删 media_item
    from sqlalchemy import text

    try:
        session.exec(text("DELETE FROM media_search_fts WHERE media_item_id=:m"), {"m": media_id})  # type: ignore[arg-type]
    except Exception:  # noqa: BLE001
        # FTS 表可能不存在(老库)或 sqlmodel 不接受 text 语法,降级 raw
        try:
            session.connection().execute(
                text("DELETE FROM media_search_fts WHERE media_item_id=:m"), {"m": media_id}
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("clean fts for %d failed: %s", media_id, e)

    session.delete(item)
    session.commit()

    # 审计
    audit_service.record(
        session,
        actor=admin,
        action="media_delete",
        target_type="media",
        target_id=media_id,
        metadata={
            "title": item.title,
            "delete_files": delete_files,
            "deleted_files_count": len(deleted_files),
            "failed_files_count": len(failed_files),
        },
        request=request,
    )

    return DeleteMediaResult(
        media_id=media_id,
        deleted_files=deleted_files,
        failed_files=failed_files,
        db_removed=True,
    )
