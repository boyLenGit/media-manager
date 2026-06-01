-- 0007_scan_dedup_phase.sql
-- 给 scan_job 增加"重复检测"阶段。扫描流程现在变成 3 阶段:
--   1. scanning   - 文件入库
--   2. enriching  - ffprobe + 缩略图
--   3. dedup      - 重复检测(在最后一个 scan job 跑完后,跨所有 scan_path 全库扫一次)
-- 只在最近一次扫描的"末尾 job"打开 dedup 阶段,避免每次小扫描都全库 O(n²)。
--
-- 字段:
--   dedup_total, dedup_done : 重复检测内部进度(组数/已对比媒体数)
--   dedup_groups_found      : 检测到的重复组数 (供前端展示 "检测到 N 个重复组")

ALTER TABLE scan_job ADD COLUMN dedup_total INTEGER NOT NULL DEFAULT 0;
ALTER TABLE scan_job ADD COLUMN dedup_done INTEGER NOT NULL DEFAULT 0;
ALTER TABLE scan_job ADD COLUMN dedup_groups_found INTEGER NOT NULL DEFAULT 0;
