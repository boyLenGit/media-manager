"""资源类型管理。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.db.session import get_session
from app.models import MediaItem, MediaType

router = APIRouter()


class MediaTypeIn(BaseModel):
    name: str
    description: str | None = None


class MediaTypeOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    media_count: int = 0


@router.get("")
def list_types(session: Session = Depends(get_session)) -> list[MediaTypeOut]:
    types = session.exec(select(MediaType).order_by(MediaType.id)).all()  # type: ignore[union-attr]
    rows = session.exec(
        select(MediaItem.media_type_id, func.count(MediaItem.id))  # type: ignore[arg-type]
        .where(MediaItem.media_type_id != None)  # noqa: E711
        .group_by(MediaItem.media_type_id)
    ).all()
    count_map = {r[0]: r[1] for r in rows}
    return [
        MediaTypeOut(
            id=t.id,  # type: ignore[arg-type]
            name=t.name,
            description=t.description,
            media_count=count_map.get(t.id, 0),
        )
        for t in types
    ]


@router.post("", status_code=201)
def create_type(payload: MediaTypeIn, session: Session = Depends(get_session)) -> MediaType:
    if session.exec(select(MediaType).where(MediaType.name == payload.name)).first():
        raise HTTPException(status_code=409, detail="type_name_taken")
    obj = MediaType(**payload.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.patch("/{type_id}")
def update_type(
    type_id: int, payload: MediaTypeIn, session: Session = Depends(get_session)
) -> MediaType:
    obj = session.get(MediaType, type_id)
    if not obj:
        raise HTTPException(status_code=404)
    if payload.name != obj.name and session.exec(
        select(MediaType).where(MediaType.name == payload.name)
    ).first():
        raise HTTPException(status_code=409, detail="type_name_taken")
    obj.name = payload.name
    obj.description = payload.description
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.delete("/{type_id}", status_code=204)
def delete_type(type_id: int, session: Session = Depends(get_session)) -> None:
    obj = session.get(MediaType, type_id)
    if not obj:
        raise HTTPException(status_code=404)
    items = session.exec(select(MediaItem).where(MediaItem.media_type_id == type_id)).all()
    for it in items:
        it.media_type_id = None
        session.add(it)
    session.delete(obj)
    session.commit()
