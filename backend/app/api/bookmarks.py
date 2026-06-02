"""书签 API。

视频时间点标记,关联到 media_item。
- 标签复用 tag 系统(通过 bookmark_tag 多对多)
- 创建者写入 created_by 字段(便于多用户场景过滤)
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.deps import require_user
from app.db.session import get_session
from app.models import Bookmark, BookmarkTag, MediaItem, Tag, User

router = APIRouter()


# ============================================================
# Schemas
# ============================================================
class BookmarkTagBrief(BaseModel):
    id: int
    name: str
    color: str | None = None
    group_name: str | None = None


class BookmarkOut(BaseModel):
    id: int
    media_item_id: int
    file_asset_id: int | None = None
    position_seconds: float
    title: str
    note: str | None = None
    created_by: int | None = None
    created_by_username: str | None = None
    tags: list[BookmarkTagBrief] = []
    created_at: datetime
    updated_at: datetime


class BookmarkCreateIn(BaseModel):
    media_item_id: int
    position_seconds: float = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)
    note: str | None = None
    file_asset_id: int | None = None
    tag_ids: list[int] = []


class BookmarkUpdateIn(BaseModel):
    position_seconds: float | None = Field(default=None, ge=0)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = None
    tag_ids: list[int] | None = None


# ============================================================
# Helpers
# ============================================================
def _build_out(session: Session, bm: Bookmark) -> BookmarkOut:
    """组装一个 BookmarkOut,带上 tag 与创建者用户名。"""
    tag_rows = session.exec(
        select(Tag.id, Tag.name, Tag.color, Tag.group_name)  # type: ignore[arg-type]
        .join(BookmarkTag, BookmarkTag.tag_id == Tag.id)  # type: ignore[arg-type]
        .where(BookmarkTag.bookmark_id == bm.id)
    ).all()
    tags = [BookmarkTagBrief(id=r[0], name=r[1], color=r[2], group_name=r[3]) for r in tag_rows]

    creator_name: str | None = None
    if bm.created_by:
        u = session.get(User, bm.created_by)
        if u:
            creator_name = u.display_name or u.username

    return BookmarkOut(
        id=bm.id,  # type: ignore[arg-type]
        media_item_id=bm.media_item_id,
        file_asset_id=bm.file_asset_id,
        position_seconds=bm.position_seconds,
        title=bm.title,
        note=bm.note,
        created_by=bm.created_by,
        created_by_username=creator_name,
        tags=tags,
        created_at=bm.created_at,
        updated_at=bm.updated_at,
    )


def _set_tags(session: Session, bookmark_id: int, tag_ids: list[int]) -> None:
    # 简化:全删全建
    existing = session.exec(
        select(BookmarkTag).where(BookmarkTag.bookmark_id == bookmark_id)
    ).all()
    for e in existing:
        session.delete(e)
    # 校验 tag 存在
    valid_ids: list[int] = []
    if tag_ids:
        rows = session.exec(select(Tag.id).where(Tag.id.in_(tag_ids))).all()  # type: ignore[union-attr]
        valid_ids = [r[0] if isinstance(r, tuple) else r for r in rows]
    for tid in valid_ids:
        session.add(BookmarkTag(bookmark_id=bookmark_id, tag_id=tid))


# ============================================================
# 路由
# ============================================================
@router.get("", response_model=list[BookmarkOut])
def list_bookmarks(
    media_item_id: int | None = Query(default=None),
    tag_id: int | None = None,
    session: Session = Depends(get_session),
) -> list[BookmarkOut]:
    """列出书签。

    - media_item_id 指定 → 按 position 升序返回该资源的所有书签
    - tag_id 指定 → 跨资源按标签筛选(用于"知识点全集"这类视图)
    - 都不传 → 返回最近 200 条
    """
    stmt = select(Bookmark)
    if media_item_id is not None:
        stmt = stmt.where(Bookmark.media_item_id == media_item_id)
    if tag_id is not None:
        stmt = stmt.join(BookmarkTag, BookmarkTag.bookmark_id == Bookmark.id).where(  # type: ignore[arg-type]
            BookmarkTag.tag_id == tag_id
        )
    if media_item_id is not None:
        stmt = stmt.order_by(Bookmark.position_seconds.asc())  # type: ignore[union-attr]
    else:
        stmt = stmt.order_by(Bookmark.created_at.desc()).limit(200)  # type: ignore[union-attr]

    rows = session.exec(stmt).all()
    return [_build_out(session, r) for r in rows]


@router.get("/{bookmark_id}", response_model=BookmarkOut)
def get_bookmark(bookmark_id: int, session: Session = Depends(get_session)) -> BookmarkOut:
    bm = session.get(Bookmark, bookmark_id)
    if not bm:
        raise HTTPException(status_code=404, detail="bookmark_not_found")
    return _build_out(session, bm)


@router.post("", response_model=BookmarkOut, status_code=201)
def create_bookmark(
    payload: BookmarkCreateIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> BookmarkOut:
    # 校验 media 存在
    if not session.get(MediaItem, payload.media_item_id):
        raise HTTPException(status_code=404, detail="media_not_found")

    bm = Bookmark(
        media_item_id=payload.media_item_id,
        file_asset_id=payload.file_asset_id,
        position_seconds=payload.position_seconds,
        title=payload.title.strip(),
        note=(payload.note.strip() if payload.note else None),
        created_by=user.id,
    )
    session.add(bm)
    session.flush()  # 拿 id

    if payload.tag_ids:
        _set_tags(session, bm.id, payload.tag_ids)  # type: ignore[arg-type]

    session.commit()
    session.refresh(bm)
    return _build_out(session, bm)


@router.patch("/{bookmark_id}", response_model=BookmarkOut)
def update_bookmark(
    bookmark_id: int,
    payload: BookmarkUpdateIn,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> BookmarkOut:
    bm = session.get(Bookmark, bookmark_id)
    if not bm:
        raise HTTPException(status_code=404, detail="bookmark_not_found")

    # 简单权限:创建者或管理员可改
    if bm.created_by and bm.created_by != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="not_owner")

    data = payload.model_dump(exclude_unset=True)
    tag_ids = data.pop("tag_ids", None)

    if "title" in data and data["title"]:
        bm.title = data["title"].strip()
    if "note" in data:
        bm.note = (data["note"].strip() if data["note"] else None)
    if "position_seconds" in data and data["position_seconds"] is not None:
        bm.position_seconds = data["position_seconds"]
    bm.updated_at = datetime.utcnow()
    session.add(bm)

    if tag_ids is not None:
        _set_tags(session, bookmark_id, tag_ids)

    session.commit()
    session.refresh(bm)
    return _build_out(session, bm)


@router.delete("/{bookmark_id}", status_code=204)
def delete_bookmark(
    bookmark_id: int,
    session: Session = Depends(get_session),
    user: User = Depends(require_user),
) -> None:
    bm = session.get(Bookmark, bookmark_id)
    if not bm:
        raise HTTPException(status_code=404, detail="bookmark_not_found")
    if bm.created_by and bm.created_by != user.id and user.role != "admin":
        raise HTTPException(status_code=403, detail="not_owner")
    # bookmark_tag 由 ON DELETE CASCADE 自动清理
    session.delete(bm)
    session.commit()


# ============================================================
# 小工具:按 media 统计书签数 (用于 UI 上 "本视频有 N 个书签" 角标)
# ============================================================
@router.get("/_count/by-media")
def count_by_media(
    media_ids: str = Query(..., description="逗号分隔 media_item_id 列表"),
    session: Session = Depends(get_session),
) -> dict[int, int]:
    """返回 {media_id: count}。前端列表批量查角标用。"""
    try:
        ids = [int(x) for x in media_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid_media_ids")
    if not ids:
        return {}
    rows = session.exec(
        select(Bookmark.media_item_id, func.count(Bookmark.id))  # type: ignore[arg-type]
        .where(Bookmark.media_item_id.in_(ids))  # type: ignore[union-attr]
        .group_by(Bookmark.media_item_id)
    ).all()
    return {r[0]: r[1] for r in rows}
