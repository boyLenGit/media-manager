"""作者管理。"""
from datetime import datetime

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.db.session import get_session
from app.models import Author, MediaItem
from app.services import author_cover_service

router = APIRouter()

MAX_COVER_SIZE_BYTES = 8 * 1024 * 1024  # 8MB


class AuthorIn(BaseModel):
    name: str
    alias: str | None = None
    description: str | None = None


class AuthorOut(BaseModel):
    id: int
    name: str
    alias: str | None = None
    description: str | None = None
    cover_path: str | None = None
    media_count: int = 0


@router.get("")
def list_authors(session: Session = Depends(get_session)) -> list[AuthorOut]:
    authors = session.exec(select(Author).order_by(Author.name)).all()  # type: ignore[union-attr]
    if not authors:
        return []

    rows = session.exec(
        select(MediaItem.author_id, func.count(MediaItem.id))  # type: ignore[arg-type]
        .where(MediaItem.author_id.in_([a.id for a in authors]))  # type: ignore[union-attr]
        .group_by(MediaItem.author_id)
    ).all()
    count_map = {r[0]: r[1] for r in rows}

    return [
        AuthorOut(
            id=a.id,  # type: ignore[arg-type]
            name=a.name,
            alias=a.alias,
            description=a.description,
            cover_path=a.cover_path,
            media_count=count_map.get(a.id, 0),
        )
        for a in authors
    ]


@router.get("/{author_id}")
def get_author(author_id: int, session: Session = Depends(get_session)) -> AuthorOut:
    obj = session.get(Author, author_id)
    if not obj:
        raise HTTPException(status_code=404, detail="author_not_found")
    count = session.exec(
        select(func.count(MediaItem.id)).where(MediaItem.author_id == author_id)  # type: ignore[arg-type]
    ).one()
    return AuthorOut(
        id=obj.id,  # type: ignore[arg-type]
        name=obj.name,
        alias=obj.alias,
        description=obj.description,
        cover_path=obj.cover_path,
        media_count=count,
    )


@router.post("", status_code=201)
def create_author(payload: AuthorIn, session: Session = Depends(get_session)) -> Author:
    if session.exec(select(Author).where(Author.name == payload.name)).first():
        raise HTTPException(status_code=409, detail="author_name_taken")
    obj = Author(**payload.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.patch("/{author_id}")
def update_author(
    author_id: int, payload: AuthorIn, session: Session = Depends(get_session)
) -> Author:
    obj = session.get(Author, author_id)
    if not obj:
        raise HTTPException(status_code=404)
    if payload.name != obj.name and session.exec(
        select(Author).where(Author.name == payload.name)
    ).first():
        raise HTTPException(status_code=409, detail="author_name_taken")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.delete("/{author_id}", status_code=204)
def delete_author(author_id: int, session: Session = Depends(get_session)) -> None:
    obj = session.get(Author, author_id)
    if not obj:
        raise HTTPException(status_code=404)
    # 把引用此作者的 media_item.author_id 置 NULL
    session.exec(
        select(MediaItem).where(MediaItem.author_id == author_id)
    )  # SQLModel 没有 update,直接逐条改
    items = session.exec(select(MediaItem).where(MediaItem.author_id == author_id)).all()
    for it in items:
        it.author_id = None
        session.add(it)
    session.delete(obj)
    session.commit()
    author_cover_service.delete_author_cover(author_id)


# ============================================================
# 封面图
# ============================================================
@router.post("/{author_id}/cover")
async def upload_author_cover(
    author_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> AuthorOut:
    obj = session.get(Author, author_id)
    if not obj:
        raise HTTPException(status_code=404, detail="author_not_found")

    ext = author_cover_service.CONTENT_TYPE_EXT_MAP.get(file.content_type or "")
    if not ext:
        raise HTTPException(status_code=400, detail="unsupported_image_type")

    data = await file.read()
    if len(data) > MAX_COVER_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="file_too_large")
    if not data:
        raise HTTPException(status_code=400, detail="empty_file")

    # 换格式时先清掉旧文件,避免残留(比如之前是 png,这次换成 jpg)
    author_cover_service.delete_author_cover(author_id)
    path = author_cover_service.get_author_cover_path(author_id, ext)
    path.write_bytes(data)

    obj.cover_path = author_cover_service.get_author_cover_url(author_id, ext)
    obj.updated_at = datetime.utcnow()
    session.add(obj)
    session.commit()
    session.refresh(obj)

    count = session.exec(
        select(func.count(MediaItem.id)).where(MediaItem.author_id == author_id)  # type: ignore[arg-type]
    ).one()
    return AuthorOut(
        id=obj.id,  # type: ignore[arg-type]
        name=obj.name,
        alias=obj.alias,
        description=obj.description,
        cover_path=obj.cover_path,
        media_count=count,
    )


@router.delete("/{author_id}/cover", status_code=204)
def remove_author_cover(author_id: int, session: Session = Depends(get_session)) -> None:
    obj = session.get(Author, author_id)
    if not obj:
        raise HTTPException(status_code=404, detail="author_not_found")
    author_cover_service.delete_author_cover(author_id)
    obj.cover_path = None
    obj.updated_at = datetime.utcnow()
    session.add(obj)
    session.commit()
