"""系统设置 API。

设计:key-value 风格,前端拿到后渲染为分类设置页。
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db.session import get_session
from app.models import AppSetting

router = APIRouter()


@router.get("")
def list_settings(session: Session = Depends(get_session)) -> list[AppSetting]:
    return session.exec(select(AppSetting)).all()


@router.put("/{key}")
def upsert_setting(key: str, payload: dict, session: Session = Depends(get_session)) -> AppSetting:
    value = payload.get("value")
    value_type = payload.get("value_type", "string")
    obj = session.exec(select(AppSetting).where(AppSetting.key == key)).first()
    if obj:
        obj.value = value
        obj.value_type = value_type
    else:
        obj = AppSetting(key=key, value=value, value_type=value_type)
        session.add(obj)
    session.commit()
    session.refresh(obj)
    return obj


@router.delete("/{key}", status_code=204)
def delete_setting(key: str, session: Session = Depends(get_session)) -> None:
    obj = session.exec(select(AppSetting).where(AppSetting.key == key)).first()
    if not obj:
        raise HTTPException(status_code=404)
    session.delete(obj)
    session.commit()
