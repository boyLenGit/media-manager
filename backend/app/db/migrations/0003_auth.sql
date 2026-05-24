-- 用户与认证 (v0003)
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT,
    role TEXT NOT NULL DEFAULT 'viewer',  -- admin / viewer
    enabled INTEGER NOT NULL DEFAULT 1,
    last_login_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_user_username ON user(username);

-- refresh token 撤销表 (登出/被踢时写入,access token 通过短过期自然失效)
CREATE TABLE IF NOT EXISTS revoked_token (
    jti TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    revoked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES user(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_revoked_token_expires ON revoked_token(expires_at);
