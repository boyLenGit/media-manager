-- Media Manager 初始化 schema (v0001)
-- 包含:核心业务表、FTS5 搜索表、初始化数据
-- 对应需求文档 v0.1 第 7/8/9 节

PRAGMA foreign_keys = ON;

-- ============================================================
-- 系统设置
-- ============================================================
CREATE TABLE IF NOT EXISTS app_setting (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key TEXT NOT NULL UNIQUE,
    value TEXT,
    value_type TEXT NOT NULL DEFAULT 'string',
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 扫描路径
-- ============================================================
CREATE TABLE IF NOT EXISTS scan_path (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    name TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    recursive INTEGER NOT NULL DEFAULT 1,
    default_media_type TEXT,
    default_tags TEXT,
    last_scan_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 搜索源
-- ============================================================
CREATE TABLE IF NOT EXISTS resource_source (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    base_url TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    auth_config TEXT,
    rate_limit_config TEXT,
    remark TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- 作者 / 类型 / 标签
-- ============================================================
CREATE TABLE IF NOT EXISTS author (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    alias TEXT,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS media_type (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS tag (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    group_name TEXT,
    color TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, group_name)
);

-- ============================================================
-- 资源条目 (作品)
-- ============================================================
CREATE TABLE IF NOT EXISTS media_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    original_title TEXT,
    normalized_title TEXT,
    media_type_id INTEGER,
    author_id INTEGER,
    release_date TEXT,
    description TEXT,
    cover_path TEXT,
    source_url TEXT,
    rating REAL,
    favorite INTEGER NOT NULL DEFAULT 0,
    watch_status TEXT NOT NULL DEFAULT 'unwatched',
    remark TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (media_type_id) REFERENCES media_type(id),
    FOREIGN KEY (author_id) REFERENCES author(id)
);
CREATE INDEX IF NOT EXISTS idx_media_item_title ON media_item(title);
CREATE INDEX IF NOT EXISTS idx_media_item_normalized_title ON media_item(normalized_title);
CREATE INDEX IF NOT EXISTS idx_media_item_author_id ON media_item(author_id);
CREATE INDEX IF NOT EXISTS idx_media_item_type_id ON media_item(media_type_id);

-- ============================================================
-- 文件资产 (具体物理文件)
-- ============================================================
CREATE TABLE IF NOT EXISTS file_asset (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_path_id INTEGER,
    path TEXT NOT NULL UNIQUE,
    directory TEXT,
    filename TEXT NOT NULL,
    extension TEXT,
    size_bytes INTEGER,
    mtime TEXT,
    sha256 TEXT,
    partial_hash TEXT,
    file_type TEXT,
    media_probe_json TEXT,
    scan_status TEXT NOT NULL DEFAULT 'active',
    missing INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scan_path_id) REFERENCES scan_path(id)
);
CREATE INDEX IF NOT EXISTS idx_file_asset_path ON file_asset(path);
CREATE INDEX IF NOT EXISTS idx_file_asset_filename ON file_asset(filename);
CREATE INDEX IF NOT EXISTS idx_file_asset_sha256 ON file_asset(sha256);
CREATE INDEX IF NOT EXISTS idx_file_asset_partial_hash ON file_asset(partial_hash);
CREATE INDEX IF NOT EXISTS idx_file_asset_size ON file_asset(size_bytes);

-- ============================================================
-- 资源-文件关联 (一作品多文件)
-- ============================================================
CREATE TABLE IF NOT EXISTS media_file (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_item_id INTEGER NOT NULL,
    file_asset_id INTEGER NOT NULL,
    version_name TEXT,
    quality TEXT,
    container TEXT,
    video_codec TEXT,
    audio_codec TEXT,
    duration_seconds REAL,
    width INTEGER,
    height INTEGER,
    subtitle_info TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (media_item_id) REFERENCES media_item(id) ON DELETE CASCADE,
    FOREIGN KEY (file_asset_id) REFERENCES file_asset(id) ON DELETE CASCADE,
    UNIQUE(media_item_id, file_asset_id)
);
CREATE INDEX IF NOT EXISTS idx_media_file_media_item_id ON media_file(media_item_id);
CREATE INDEX IF NOT EXISTS idx_media_file_file_asset_id ON media_file(file_asset_id);

-- ============================================================
-- 资源-标签关联
-- ============================================================
CREATE TABLE IF NOT EXISTS media_tag (
    media_item_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (media_item_id, tag_id),
    FOREIGN KEY (media_item_id) REFERENCES media_item(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tag(id) ON DELETE CASCADE
);

-- ============================================================
-- 搜索结果 (引用 media_item,放在它后面)
-- ============================================================
CREATE TABLE IF NOT EXISTS search_result (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    title TEXT NOT NULL,
    normalized_title TEXT,
    magnet_uri TEXT,
    info_hash TEXT,
    size_bytes INTEGER,
    publish_time TEXT,
    source_url TEXT,
    raw_json TEXT,
    duplicate_level TEXT DEFAULT 'none',
    matched_media_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_id) REFERENCES resource_source(id),
    FOREIGN KEY (matched_media_id) REFERENCES media_item(id)
);
CREATE INDEX IF NOT EXISTS idx_search_result_info_hash ON search_result(info_hash);
CREATE INDEX IF NOT EXISTS idx_search_result_title ON search_result(title);
CREATE INDEX IF NOT EXISTS idx_search_result_normalized_title ON search_result(normalized_title);

-- ============================================================
-- 下载任务
-- ============================================================
CREATE TABLE IF NOT EXISTS download_task (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_result_id INTEGER,
    title TEXT NOT NULL,
    magnet_uri TEXT,
    info_hash TEXT,
    downloader TEXT NOT NULL DEFAULT 'qbittorrent',
    downloader_task_id TEXT,
    save_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    progress REAL NOT NULL DEFAULT 0,
    download_speed INTEGER DEFAULT 0,
    upload_speed INTEGER DEFAULT 0,
    eta_seconds INTEGER,
    error_message TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (search_result_id) REFERENCES search_result(id)
);
CREATE INDEX IF NOT EXISTS idx_download_task_info_hash ON download_task(info_hash);
CREATE INDEX IF NOT EXISTS idx_download_task_status ON download_task(status);

-- ============================================================
-- 播放目标 / 播放历史
-- ============================================================
CREATE TABLE IF NOT EXISTS playback_target (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    target_type TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    config_json TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS playback_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_item_id INTEGER NOT NULL,
    file_asset_id INTEGER,
    playback_target_id INTEGER,
    position_seconds REAL NOT NULL DEFAULT 0,
    duration_seconds REAL,
    completed INTEGER NOT NULL DEFAULT 0,
    played_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (media_item_id) REFERENCES media_item(id) ON DELETE CASCADE,
    FOREIGN KEY (file_asset_id) REFERENCES file_asset(id),
    FOREIGN KEY (playback_target_id) REFERENCES playback_target(id)
);

-- ============================================================
-- 去重匹配
-- ============================================================
CREATE TABLE IF NOT EXISTS duplicate_match (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    matched_media_id INTEGER,
    matched_file_id INTEGER,
    match_level TEXT NOT NULL,
    match_reason TEXT,
    score REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (matched_media_id) REFERENCES media_item(id),
    FOREIGN KEY (matched_file_id) REFERENCES file_asset(id)
);

-- ============================================================
-- 扫描任务 / 扫描日志
-- ============================================================
CREATE TABLE IF NOT EXISTS scan_job (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_path_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending',
    total_files INTEGER NOT NULL DEFAULT 0,
    scanned_files INTEGER NOT NULL DEFAULT 0,
    new_files INTEGER NOT NULL DEFAULT 0,
    updated_files INTEGER NOT NULL DEFAULT 0,
    missing_files INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scan_path_id) REFERENCES scan_path(id)
);

CREATE TABLE IF NOT EXISTS scan_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_job_id INTEGER,
    level TEXT NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    file_path TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (scan_job_id) REFERENCES scan_job(id) ON DELETE CASCADE
);

-- ============================================================
-- FTS5 全文搜索
-- ============================================================
CREATE VIRTUAL TABLE IF NOT EXISTS media_search_fts USING fts5(
    media_item_id UNINDEXED,
    title,
    original_title,
    normalized_title,
    author_name,
    tag_names,
    description,
    filenames,
    paths
);
