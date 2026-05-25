"""应用配置,基于 pydantic-settings,从环境变量或 .env 加载。"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用
    app_name: str = "Media Manager"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False

    # 认证
    jwt_secret: str = "change-me-in-production-use-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7

    # 数据
    data_dir: Path = Path("./data")
    database_url: str = "sqlite:///./data/media_manager.db"
    static_dir: Path = Path("../frontend/dist")

    # CORS
    cors_origins: str = "http://localhost:5173"

    # qBittorrent
    qbittorrent_url: str = ""
    qbittorrent_username: str = ""
    qbittorrent_password: str = ""

    # Jellyfin
    jellyfin_url: str = ""
    jellyfin_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_dirs()
    return settings
