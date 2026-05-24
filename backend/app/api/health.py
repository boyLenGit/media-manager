"""健康检查与系统信息。"""
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter

from app.providers.downloader import factory as dl_factory
from app.providers.player import factory as jf_factory

router = APIRouter()


def _read_build_info() -> dict:
    """从镜像里的 /app/VERSION 和 /app/COMMIT 读版本(由 CI 写入)。"""
    info: dict[str, str] = {}
    for key, env_key, file_name in [
        ("version", "BUILD_VERSION", "/app/VERSION"),
        ("commit", "BUILD_COMMIT", "/app/COMMIT"),
    ]:
        value = os.environ.get(env_key, "")
        if not value:
            try:
                value = Path(file_name).read_text(encoding="utf-8").strip()
            except Exception:  # noqa: BLE001
                value = ""
        info[key] = value or "dev"
    return info


@router.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "time": datetime.utcnow().isoformat() + "Z",
        **_read_build_info(),
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
        **_read_build_info(),
    }
