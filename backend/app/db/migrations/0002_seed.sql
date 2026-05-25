-- 初始化基础数据 (幂等执行,使用 OR IGNORE)
INSERT OR IGNORE INTO media_type (name, description) VALUES
    ('movie', '电影'),
    ('series', '剧集'),
    ('anime', '动画'),
    ('course', '课程'),
    ('documentary', '纪录片'),
    ('short_video', '短视频'),
    ('music_video', '音乐视频'),
    ('other', '其他');

INSERT OR IGNORE INTO tag (name, group_name, color) VALUES
    ('未看', '状态', '#999999'),
    ('已看', '状态', '#4caf50'),
    ('收藏', '状态', '#ff9800'),
    ('高清', '清晰度', '#2196f3'),
    ('4K', '清晰度', '#673ab7'),
    ('中文字幕', '语言', '#009688'),
    ('英语', '语言', '#3f51b5'),
    ('待整理', '管理', '#f44336');

INSERT OR IGNORE INTO playback_target (name, target_type, enabled, config_json, sort_order) VALUES
    ('网页播放', 'web', 1, '{}', 10),
    ('Jellyfin 播放', 'jellyfin', 0, '{}', 20),
    ('复制播放链接', 'external_url', 1, '{}', 30),
    ('复制 SMB 路径', 'smb_path', 0, '{}', 40),
    ('打开所在目录', 'reveal_dir', 1, '{}', 45),
    ('自定义协议播放', 'custom_protocol', 0, '{"scheme":"media-manager"}', 50);
