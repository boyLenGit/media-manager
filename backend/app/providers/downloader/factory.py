"""下载器工厂。从 app_setting 读配置创建 Provider 实例。"""
import json
import logging
from typing import Optional

from sqlmodel import Session, select

from app.core.config import get_settings
from app.db.session import engine
from app.models import AppSetting
from app.providers.downloader.base import DownloaderProvider
from app.providers.downloader.qbittorrent import QBittorrentProvider

logger = logging.getLogger(__name__)

# 设置 key
SETTING_KEY = "downloader_config"


def _read_setting() -> dict:
    """从 settings 表读取下载器配置;没有则回落到 .env。"""
    with Session(engine) as session:
        s = session.exec(select(AppSetting).where(AppSetting.key == SETTING_KEY)).first()
    if s and s.value:
        try:
            return json.loads(s.value)
        except json.JSONDecodeError:
            logger.warning("downloader_config json invalid")

    # fallback to env
    env = get_settings()
    return {
        "provider": "qbittorrent",
        "url": env.qbittorrent_url,
        "username": env.qbittorrent_username,
        "password": env.qbittorrent_password,
    }


def is_configured() -> bool:
    cfg = _read_setting()
    return bool(cfg.get("url") and cfg.get("username"))


def save_setting(payload: dict) -> None:
    """保存配置到 settings 表。"""
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
                description="下载器配置 (provider/url/username/password)",
            )
            session.add(s)
        session.commit()


def create_provider() -> Optional[DownloaderProvider]:
    """根据配置创建 provider,未配置返回 None。"""
    cfg = _read_setting()
    if not cfg.get("url"):
        return None
    provider_type = cfg.get("provider", "qbittorrent")
    if provider_type == "qbittorrent":
        return QBittorrentProvider(
            base_url=cfg["url"],
            username=cfg.get("username", ""),
            password=cfg.get("password", ""),
        )
    raise ValueError(f"unsupported downloader provider: {provider_type}")


async def health_check() -> dict:
    """连通性测试。"""
    cfg = _read_setting()
    if not cfg.get("url"):
        return {"ok": False, "error": "not_configured"}
    p = create_provider()
    if not p:
        return {"ok": False, "error": "create_failed"}
    try:
        ok = await p.health_check()  # type: ignore[union-attr]
        return {"ok": ok, "provider": cfg.get("provider"), "url": cfg["url"]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)}
    finally:
        if hasattr(p, "close"):
            await p.close()
