-- 0005_scan_job_phases.sql
-- 给 scan_job 增加"后处理阶段"(ffprobe + 缩略图)的进度字段。
--
-- 背景:
-- 旧版只有 scanned_files / total_files,扫完文件就把 status 改成 success,
-- 但其实后台还在跑 ffprobe + 缩略图(可能持续几分钟到十几分钟),用户看不到进度。
--
-- 现在拆成两个阶段:
--   - 阶段 1: 扫描文件元数据(stat, hash, 入库) → scanned_files/total_files
--   - 阶段 2: 后处理(ffprobe + 缩略图)        → enrich_done/enrich_total
--
-- 同时新增 status 'enriching' 表示阶段 2 进行中。
-- 'success' 仅在两阶段都完成后才设置。

ALTER TABLE scan_job ADD COLUMN enrich_total INTEGER NOT NULL DEFAULT 0;
ALTER TABLE scan_job ADD COLUMN enrich_done INTEGER NOT NULL DEFAULT 0;
ALTER TABLE scan_job ADD COLUMN phase TEXT NOT NULL DEFAULT 'scanning';
-- phase 取值:
--   scanning  - 阶段 1: 扫描文件
--   enriching - 阶段 2: ffprobe + 缩略图生成
--   done      - 完成(无论 success 还是 failed)
