"""SQLModel ORM 模型,字段对齐 db/migrations/0001_init.sql。

设计原则:
- 表结构以 SQL 迁移文件为准,这里只做映射
- 关系暂不通过 ORM relationship 体现,服务层显式 JOIN,降低复杂度
"""
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, Text
from pydantic import model_serializer
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.utcnow()


class UTCAwareModel(SQLModel):
    """所有 datetime 字段在库内统一存 naive UTC(datetime.utcnow()),
    但序列化给前端时必须带明确的 UTC 标记,否则浏览器 Date() 会把它误当成本地时间解析,
    导致显示时间偏移(实际偏移量 = 本地时区与 UTC 的差值,如东八区偏移 8 小时)。

    这里在序列化阶段统一补上时区标记(不修改原对象状态),
    比在每个 API 接口手动 `.isoformat() + "Z"` 更不容易遗漏。
    """

    @model_serializer(mode="wrap")
    def _serialize_with_utc(self, handler) -> dict[str, Any]:
        data = handler(self)
        for k in list(data.keys()):
            raw = getattr(self, k, None)
            if isinstance(raw, datetime) and raw.tzinfo is None and isinstance(data.get(k), str):
                data[k] = raw.replace(tzinfo=timezone.utc).isoformat()
        return data


class TimestampMixin(UTCAwareModel):
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
    cover_path: Optional[str] = None


class MediaType(UTCAwareModel, table=True):
    __tablename__ = "media_type"
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class Tag(UTCAwareModel, table=True):
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
# 自定义字幕(用户手动上传/替换,独立存储于应用数据目录)
# ============================================================
class CustomSubtitle(UTCAwareModel, table=True):
    __tablename__ = "custom_subtitle"
    id: Optional[int] = Field(default=None, primary_key=True)
    file_asset_id: int = Field(foreign_key="file_asset.id", index=True)
    filename: str
    extension: str
    language_hint: Optional[str] = None
    size_bytes: Optional[int] = None
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ============================================================
# 资源-文件关联
# ============================================================
class MediaFile(UTCAwareModel, table=True):
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


class MediaTag(UTCAwareModel, table=True):
    __tablename__ = "media_tag"
    media_item_id: int = Field(foreign_key="media_item.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)
    created_at: datetime = Field(default_factory=_now)


# ============================================================
# 搜索结果
# ============================================================
class SearchResult(UTCAwareModel, table=True):
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


class PlaybackHistory(UTCAwareModel, table=True):
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
class DuplicateMatch(UTCAwareModel, table=True):
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


class ScanJob(UTCAwareModel, table=True):
    __tablename__ = "scan_job"
    id: Optional[int] = Field(default=None, primary_key=True)
    scan_path_id: Optional[int] = Field(default=None, foreign_key="scan_path.id")
    # status: pending / running / enriching / success / failed
    # 'running'   - 阶段1: 扫描文件入库
    # 'enriching' - 阶段2: ffprobe + 缩略图生成 (扫描已完成,但还在做后处理)
    status: str = "pending"
    # phase: scanning / enriching / dedup / done (用来在前端显示阶段名,与 status 互补)
    phase: str = "scanning"
    total_files: int = 0
    scanned_files: int = 0
    new_files: int = 0
    updated_files: int = 0
    missing_files: int = 0
    # 阶段2 的进度
    enrich_total: int = 0
    enrich_done: int = 0
    # 阶段3 的进度 (重复检测,仅末尾 job 跑)
    dedup_total: int = 0
    dedup_done: int = 0
    dedup_groups_found: int = 0
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_now)


class ScanLog(UTCAwareModel, table=True):
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


class RevokedToken(UTCAwareModel, table=True):
    __tablename__ = "revoked_token"
    jti: str = Field(primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    revoked_at: datetime = Field(default_factory=_now)
    expires_at: datetime


class AuditLog(UTCAwareModel, table=True):
    """系统审计日志(append-only)。

    用于记录敏感操作(危险区清空、删除资源等),便于追责与排错。
    """

    __tablename__ = "audit_log"
    id: Optional[int] = Field(default=None, primary_key=True)
    actor_user_id: Optional[int] = Field(default=None, foreign_key="user.id")
    actor_username: Optional[str] = None  # 冗余,即使用户删了也能查到
    action: str  # 'reset_all', 'media_delete', etc.
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    # JSON TEXT;字段名故意叫 metadata_json 避免与 SQLAlchemy declarative 'metadata' 冲突
    metadata_json: Optional[str] = Field(default=None, sa_column=Column("metadata", Text))
    ip: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class Bookmark(UTCAwareModel, table=True):
    """视频时间点书签。

    一个书签 = (media_item, 时间秒, 标题, [可选 note], [多个 tag])
    标签复用 tag 表,通过 bookmark_tag 多对多挂上。
    """

    __tablename__ = "bookmark"
    id: Optional[int] = Field(default=None, primary_key=True)
    media_item_id: int = Field(foreign_key="media_item.id")
    file_asset_id: Optional[int] = Field(default=None, foreign_key="file_asset.id")
    position_seconds: float
    title: str
    note: Optional[str] = None
    created_by: Optional[int] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class BookmarkTag(SQLModel, table=True):
    """书签 ↔ 标签的多对多。"""

    __tablename__ = "bookmark_tag"
    bookmark_id: int = Field(foreign_key="bookmark.id", primary_key=True)
    tag_id: int = Field(foreign_key="tag.id", primary_key=True)
