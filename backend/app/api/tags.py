"""标签管理。"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select

from app.db.session import get_session
from app.models import MediaTag, Tag

router = APIRouter()


class TagIn(BaseModel):
    name: str
    group_name: str | None = None
    color: str | None = None


class TagOut(BaseModel):
    id: int
    name: str
    group_name: str | None = None
    color: str | None = None
    media_count: int = 0


@router.get("")
def list_tags(session: Session = Depends(get_session)) -> list[TagOut]:
    tags = session.exec(select(Tag).order_by(Tag.group_name, Tag.name)).all()  # type: ignore[union-attr]
    if not tags:
        return []
    rows = session.exec(
        select(MediaTag.tag_id, func.count(MediaTag.media_item_id))  # type: ignore[arg-type]
        .where(MediaTag.tag_id.in_([t.id for t in tags]))  # type: ignore[union-attr]
        .group_by(MediaTag.tag_id)
    ).all()
    count_map = {r[0]: r[1] for r in rows}
    return [
        TagOut(
            id=t.id,  # type: ignore[arg-type]
            name=t.name,
            group_name=t.group_name,
            color=t.color,
            media_count=count_map.get(t.id, 0),
        )
        for t in tags
    ]


@router.post("", status_code=201)
def create_tag(payload: TagIn, session: Session = Depends(get_session)) -> Tag:
    # 同 (name, group_name) 唯一
    existing = session.exec(
        select(Tag).where(Tag.name == payload.name, Tag.group_name == payload.group_name)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="tag_already_exists")
    obj = Tag(**payload.model_dump())
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.patch("/{tag_id}")
def update_tag(tag_id: int, payload: TagIn, session: Session = Depends(get_session)) -> Tag:
    obj = session.get(Tag, tag_id)
    if not obj:
        raise HTTPException(status_code=404)
    obj.name = payload.name
    obj.group_name = payload.group_name
    obj.color = payload.color
    session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.delete("/{tag_id}", status_code=204)
def delete_tag(tag_id: int, session: Session = Depends(get_session)) -> None:
    obj = session.get(Tag, tag_id)
    if not obj:
        raise HTTPException(status_code=404)
    # ON DELETE CASCADE 会自动删 media_tag
    session.delete(obj)
    session.commit()
