-- 0010_custom_subtitle.sql
-- 用户手动上传的自定义字幕(上传 / 替换字幕功能)。
--
-- 设计:
--   - 与现有"同目录文件名自动匹配"字幕机制(files.py::list_subtitles,纯运行时动态匹配,
--     不落库)不同,自定义字幕需要持久化的绑定关系,直接关联到具体的 file_asset_id(视频文件),
--     不关联 media_item_id —— 因为一个 media_item 可能有多个视频文件版本,字幕应精确绑定到
--     某一个具体文件,不应该在多版本间共享错配。
--   - 物理存储在应用数据目录 data/custom_subtitles/<id>.<ext>,不写入只读挂载的原始媒体目录
--     (视频目录当前是 :ro 挂载,遵循项目"真实磁盘文件默认不动"的原则)。
--   - 上传时立即做编码检测转 UTF-8(复用 subtitle_encoding 模块)后落盘,存储的内容始终是
--     规范 UTF-8,播放时不需要二次转码。
--   - 同一个视频允许有多条自定义字幕(比如中文/日文/双语版各一份),用户可自行删除替换。

CREATE TABLE IF NOT EXISTS custom_subtitle (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_asset_id INTEGER NOT NULL,
    filename TEXT NOT NULL,             -- 原始上传文件名(用于展示)
    extension TEXT NOT NULL,            -- 规范化扩展名(不含点),如 srt/ass/vtt
    language_hint TEXT,                 -- 用户可选填写的语言标签,如 "中文"/"日文双语"
    size_bytes INTEGER,
    created_by INTEGER,                 -- 上传者 user_id,可空
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (file_asset_id) REFERENCES file_asset(id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES user(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_custom_subtitle_file_asset ON custom_subtitle(file_asset_id);
