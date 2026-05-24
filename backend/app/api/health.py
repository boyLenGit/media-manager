"""健康检查与系统信息。"""
from datetime import datetime

from fastapi import APIRouter

from app.providers.downloader import factory as dl_factory
from app.providers.player import factory as jf_factory

router = APIRouter()


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/info")
def info() -> dict:
    from app.core.config import get_settings

    s = get_settings()
    return {
        "app_name": s.app_name,
        "debug": s.app_debug,
        "qbittorrent_configured": dl_factory.is_configured(),
        "jellyfin_configured": jf_factory.is_configured(),
    }
