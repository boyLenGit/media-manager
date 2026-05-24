"""作者管理。"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.db.session import get_session
from app.models import Author, MediaItem

router = APIRouter()


class AuthorIn(BaseModel):
    name: str
    alias: str | None = None
    description: str | None = None


class AuthorOut(BaseModel):
    id: int
    name: str
    alias: str | None = None
    description: str | None = None
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
            media_count=count_map.get(a.id, 0),
        )
        for a in authors
    ]


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
