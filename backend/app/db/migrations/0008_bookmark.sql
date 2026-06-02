-- 0008_bookmark.sql
-- 视频书签 / 时间点标记。
--
-- 设计:
--   - 一个书签 = (media_item, position_seconds, title)
--   - 标签复用现有 tag 表,通过 bookmark_tag 多对多挂上(便于做"知识点"这类标签体系)
--   - note 是富文本说明(可空),title 是必填的简短描述
--   - 关联 user 让多用户场景下可看到"是谁打的"

CREATE TABLE IF NOT EXISTS bookmark (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_item_id INTEGER NOT NULL,
    -- file_asset_id 可选:多文件资源时记录是哪个文件的时间点;为空则按主文件
    file_asset_id INTEGER,
    position_seconds REAL NOT NULL,
    title TEXT NOT NULL,
    note TEXT,
    created_by INTEGER,                -- 创建者 user_id;系统迁移历史可为空
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (media_item_id) REFERENCES media_item(id) ON DELETE CASCADE,
    FOREIGN KEY (file_asset_id) REFERENCES file_asset(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES user(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_bookmark_media ON bookmark(media_item_id, position_seconds);
CREATE INDEX IF NOT EXISTS idx_bookmark_creator ON bookmark(created_by);

CREATE TABLE IF NOT EXISTS bookmark_tag (
    bookmark_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (bookmark_id, tag_id),
    FOREIGN KEY (bookmark_id) REFERENCES bookmark(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tag(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_bookmark_tag_tag ON bookmark_tag(tag_id);
