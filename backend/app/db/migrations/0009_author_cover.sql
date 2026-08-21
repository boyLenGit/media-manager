-- 0009_author_cover.sql
-- 作者封面图。
--
-- 设计:
--   - cover_path 存相对 URL(风格对齐 media_item.cover_path),实际图片走独立的
--     /api/author-covers/<id>.<ext> 静态路由(仿 media 缩略图),文件存 data/author_covers/<id>.<ext>
--   - 支持用户手动上传 jpg/png/webp,与 media 缩略图(扫描时 ffmpeg 自动截帧生成)不同,
--     不会被扫描流程覆盖,只能通过作者详情页手动更换/移除

ALTER TABLE author ADD COLUMN cover_path TEXT;
