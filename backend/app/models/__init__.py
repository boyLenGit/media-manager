"""SQLModel ORM 模型,字段对齐 db/migrations/0001_init.sql。

设计原则:
- 表结构以 SQL 迁移文件为准,这里只做映射
- 关系暂不通过 ORM relationship 体现,服务层显式 JOIN,降低复杂度
"""
from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.utcnow()


class TimestampMixin(SQLModel):
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ============================================================
# 系统设置
# ============================================================
class AppSetting(TimestampMixin, table=True):
    __tablename__ = "app_setting"
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(unique=True, index=True)
    value: Optional[str] = None
    value_type: str = "string"
    description: Optional[str] = None


# ============================================================
# 扫描路径
# ============================================================
class ScanPath(TimestampMixin, table=True):
    __tablename__ = "scan_path"
    id: Optional[int] = Field(default=None, primary_key=True)
    path: str = Field(unique=True, index=True)
    name: Optional[str] = None
    enabled: bool = True
    recursive: bool = True
    default_media_type: Optional[str] = None
    default_tags: Optional[str] = None  # JSON string
    last_scan_at: Optional[datetime] = None


# ============================================================
# 搜索源
# ============================================================
class ResourceSource(TimestampMixin, table=True):
    __tablename__ = "resource_source"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    source_type: str  # magnet_api / rss / manual / custom_plugin
    base_url: Optional[str] = None
    enabled: bool = True
    auth_config: Optional[str] = None  # JSON
    rate_limit_config: Optional[str] = None  # JSON
    remark: Optional[str] = None


# ============================================================
# 作者 / 类型 / 标签
# ============================================================
class Author(TimestampMixin, table=True):
    __tablename__ = "author"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    alias: Optional[str] = None
    description: Optional[str] = None


class MediaType(SQLModel, table=True):
    __tablename__ = "media_type"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class Tag(SQLModel, table=True):
    __tablename__ = "tag"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    group_name: Optional[str] = None
    color: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


# ============================================================
# 资源条目
# ============================================================
class MediaItem(TimestampMixin, table=True):
    __tablename__ = "media_item"
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    original_title: Optional[str] = None
    normalized_title: Optional[str] = Field(default=None, index=True)
    media_type_id: Optional[int] = Field(default=None, foreign_key="media_type.id", index=True)
    author_id: Optional[int] = Field(default=None, foreign_key="author.id", index=True)
    release_date: Optional[str] = None
    description: Optional[str] = None
    cover_path: Optional[str] = None
    source_url: Optional[str] = None
    rating: Optional[float] = None
    favorite: bool = False
    watch_status: str = "unwatched"  # unwatched / watching / watched
    remark: Optional[str] = None


# ============================================================
# 文件资产
# ============================================================
class FileAsset(TimestampMixin, table=True):
    __tablename__ = "file_asset"
    id: Optional[int] = Field(default=None, primary_key=True)
    scan_path_id: Optional[int] = Field(default=None, foreign_key="scan_path.id")
    path: str = Field(unique=True, index=True)
    directory: Optional[str] = None
    filename: str = Field(index=True)
    extension: Optional[str] = None
    size_bytes: Optional[int] = Field(default=None, index=True)
    mtime: Optional[datetime] = None
    sha256: Optional[str] = Field(default=None, index=True)
    partial_hash: Optional[str] = Field(default=None, index=True)
    file_type: Optional[str] = None  # video / subtitle / image / metadata
    media_probe_json: Optional[str] = None
    scan_status: str = "active"
    missing: bool = False


# ============================================================
# 资源-文件关联
# ============================================================
class MediaFile(SQLModel, table=True):
    __tablename__ = "media_file"
    id: Optional[int] = Field(default=None, primary_key=True)
    media_item_id: int = Field(foreign_key="media_item.id", index=True)
    file_asset_id: int = Field(foreign_key="file_asset.id", index=True)
    version_name: Optional[str] = None
    quality: Optional[str] = None
    container: Optional[str] = None
    video_codec: Optional[str] = None
    audio_codec: Optional[str] = None
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    subtitle_info: Optional[str] = None  # JSON
    is_primary: bool = False
    created_at: datetime = Field(default_factory=_now)


class MediaTag(SQLModel, table=True):
    __tablename__ = "media_tag"
    media_item_id: int = Field(foreign_key="media_item.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)
    created_at: datetime = Field(default_factory=_now)


# ============================================================
# 搜索结果
# ============================================================
class SearchResult(SQLModel, table=True):
    __tablename__ = "search_result"
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: Optional[int] = Field(default=None, foreign_key="resource_source.id")
    title: str
    normalized_title: Optional[str] = Field(default=None, index=True)
    magnet_uri: Optional[str] = None
    info_hash: Optional[str] = Field(default=None, index=True)
    size_bytes: Optional[int] = None
    publish_time: Optional[datetime] = None
    source_url: Optional[str] = None
    raw_json: Optional[str] = None
    duplicate_level: str = "none"
    matched_media_id: Optional[int] = Field(default=None, foreign_key="media_item.id")
    created_at: datetime = Field(default_factory=_now)


# ============================================================
# 下载任务
# ============================================================
class DownloadTask(TimestampMixin, table=True):
    __tablename__ = "download_task"
    id: Optional[int] = Field(default=None, primary_key=True)
    search_result_id: Optional[int] = Field(default=None, foreign_key="search_result.id")
    title: str
    magnet_uri: Optional[str] = None
    info_hash: Optional[str] = Field(default=None, index=True)
    downloader: str = "qbittorrent"
    downloader_task_id: Optional[str] = None
    save_path: Optional[str] = None
    status: str = Field(default="pending", index=True)
    progress: float = 0.0
    download_speed: int = 0
    upload_speed: int = 0
    eta_seconds: Optional[int] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# ============================================================
# 播放
# ============================================================
class PlaybackTarget(TimestampMixin, table=True):
    __tablename__ = "playback_target"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    target_type: str  # web / jellyfin / external_url / smb_path / reveal_dir / custom_protocol
    enabled: bool = True
    config_json: Optional[str] = None
    sort_order: int = 0


class PlaybackHistory(SQLModel, table=True):
    __tablename__ = "playback_history"
    id: Optional[int] = Field(default=None, primary_key=True)
    media_item_id: int = Field(foreign_key="media_item.id")
    file_asset_id: Optional[int] = Field(default=None, foreign_key="file_asset.id")
    playback_target_id: Optional[int] = Field(default=None, foreign_key="playback_target.id")
    position_seconds: float = 0.0
    duration_seconds: Optional[float] = None
    completed: bool = False
    played_at: datetime = Field(default_factory=_now)


# ============================================================
# 去重 / 扫描
# ============================================================
class DuplicateMatch(SQLModel, table=True):
    __tablename__ = "duplicate_match"
    id: Optional[int] = Field(default=None, primary_key=True)
    target_type: str  # search_result / file_asset
    target_id: int
    matched_media_id: Optional[int] = Field(default=None, foreign_key="media_item.id")
    matched_file_id: Optional[int] = Field(default=None, foreign_key="file_asset.id")
    match_level: str  # exact / high / medium / low / none
    match_reason: Optional[str] = None
    score: Optional[float] = None
    created_at: datetime = Field(default_factory=_now)


class ScanJob(SQLModel, table=True):
    __tablename__ = "scan_job"
    id: Optional[int] = Field(default=None, primary_key=True)
    scan_path_id: Optional[int] = Field(default=None, foreign_key="scan_path.id")
    status: str = "pending"  # pending / running / success / failed
    total_files: int = 0
    scanned_files: int = 0
    new_files: int = 0
    updated_files: int = 0
    missing_files: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_now)


class ScanLog(SQLModel, table=True):
    __tablename__ = "scan_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    scan_job_id: Optional[int] = Field(default=None, foreign_key="scan_job.id")
    level: str = "info"
    message: str
    file_path: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


# ============================================================
# 用户认证
# ============================================================
class User(TimestampMixin, table=True):
    __tablename__ = "user"
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    display_name: Optional[str] = None
    role: str = "viewer"  # admin / viewer
    enabled: bool = True
    last_login_at: Optional[datetime] = None


class RevokedToken(SQLModel, table=True):
    __tablename__ = "revoked_token"
    jti: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    revoked_at: datetime = Field(default_factory=_now)
    expires_at: datetime
