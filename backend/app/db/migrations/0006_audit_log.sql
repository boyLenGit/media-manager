-- 0006_audit_log.sql
-- 系统审计日志,记录敏感操作(目前主要是危险区操作,后续可拓展)。
--
-- 设计原则:
--   - 一条记录一行,actor / action / target / metadata 四元组
--   - metadata 用 JSON TEXT,字段灵活
--   - 仅追加,不允许从 UI 删除(便于追责)
--   - 体量预期很小(几个月几百条),不做分区

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    actor_user_id INTEGER,           -- 触发用户;允许 NULL(系统自动操作)
    actor_username TEXT,             -- 冗余存,即使用户被删也能看到是谁干的
    action TEXT NOT NULL,            -- 'reset_all' / 'media_delete' / ...
    target_type TEXT,                -- 'media' / 'user' / 'system' / NULL
    target_id TEXT,                  -- 资源 ID(字符串以兼容多种类型)
    metadata TEXT,                   -- JSON,操作上下文(影响范围、参数等)
    ip TEXT,                         -- 客户端 IP(若可拿到)
    user_agent TEXT,                 -- 客户端 UA(若可拿到)
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (actor_user_id) REFERENCES user(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_actor ON audit_log(actor_user_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at DESC);
