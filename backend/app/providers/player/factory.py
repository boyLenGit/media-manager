"""Jellyfin 配置工厂。"""
import json
import logging

from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import engine
from app.models import AppSetting
from app.providers.player.jellyfin import JellyfinProvider

logger = logging.getLogger(__name__)

SETTING_KEY = "jellyfin_config"


def read_config() -> dict:
    with Session(engine) as session:
        s = session.exec(select(AppSetting).where(AppSetting.key == SETTING_KEY)).first()
    if s and s.value:
        try:
            return json.loads(s.value)
        except json.JSONDecodeError:
            pass
    env = get_settings()
    return {"url": env.jellyfin_url, "api_key": env.jellyfin_api_key}


def save_config(payload: dict) -> None:
    with Session(engine) as session:
        s = session.exec(select(AppSetting).where(AppSetting.key == SETTING_KEY)).first()
        if s:
            s.value = json.dumps(payload, ensure_ascii=False)
            s.value_type = "json"
        else:
            s = AppSetting(
                key=SETTING_KEY,
                value=json.dumps(payload, ensure_ascii=False),
                value_type="json",
                description="Jellyfin 配置",
            )
            session.add(s)
        session.commit()


def is_configured() -> bool:
    cfg = read_config()
    return bool(cfg.get("url") and cfg.get("api_key"))


def create_provider() -> JellyfinProvider | None:
    cfg = read_config()
    if not cfg.get("url"):
        return None
    return JellyfinProvider(base_url=cfg["url"], api_key=cfg.get("api_key", ""))
