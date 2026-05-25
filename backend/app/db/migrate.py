"""轻量级 SQL 迁移执行器。

设计目标:
- 不引入 Alembic,避免依赖
- 按文件名排序顺序执行 db/migrations/*.sql
- 用 schema_version 表记录已执行的版本,保证幂等
"""
import logging
import shutil
from pathlib import Path

from sqlalchemy import text

from app.core.config import get_settings
from app.db.session import engine

logger = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def _ensure_version_table() -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def _applied_versions() -> set[str]:
    with engine.begin() as conn:
        rows = conn.execute(text("SELECT version FROM schema_version")).all()
    return {r[0] for r in rows}


def _apply_migration(path: Path) -> None:
    sql = path.read_text(encoding="utf-8")
    version = path.stem
    logger.info("Applying migration: %s", version)
    with engine.begin() as conn:
        # SQLite 不支持一次执行多语句,需要拆分
        for stmt in _split_sql_statements(sql):
            if stmt.strip():
                conn.exec_driver_sql(stmt)
        conn.execute(
            text("INSERT INTO schema_version (version) VALUES (:v)"),
            {"v": version},
        )


def _split_sql_statements(sql: str) -> list[str]:
    """简单按分号分割,忽略行注释。

    注意: 当前 schema 不包含触发器/存储过程,简单分号分割够用。
    后续若有 BEGIN...END 块需要换更复杂的解析。
    """
    statements: list[str] = []
    buf: list[str] = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") or not stripped:
            continue
        buf.append(line)
        if stripped.endswith(";"):
            statements.append("\n".join(buf))
            buf = []
    if buf:
        statements.append("\n".join(buf))
    return statements


def _migrate_legacy_db_file() -> None:
    """品牌改名后,把旧的 mediahub.db 自动改名为 media_manager.db。

    仅当 media_manager.db 不存在且 mediahub.db 存在时执行,避免覆盖新数据。
    包括 -wal 和 -shm 副文件。
    """
    settings = get_settings()
    if "media_manager.db" not in settings.database_url:
        return  # 用户用的是其他路径,不动

    data_dir = settings.data_dir
    new_db = data_dir / "media_manager.db"
    legacy_db = data_dir / "mediahub.db"

    if new_db.exists() or not legacy_db.exists():
        return

    logger.info(
        "Found legacy database %s, renaming to %s (rebranding from MediaHub → Media Manager)",
        legacy_db,
        new_db,
    )
    try:
        shutil.move(str(legacy_db), str(new_db))
        # WAL/SHM 文件也跟着搬,SQLite 会基于主 db 名字找
        for suffix in ("-wal", "-shm"):
            old = data_dir / f"mediahub.db{suffix}"
            new = data_dir / f"media_manager.db{suffix}"
            if old.exists() and not new.exists():
                shutil.move(str(old), str(new))
        logger.info("Legacy database migration done.")
    except OSError as e:
        logger.error("Failed to migrate legacy db: %s", e)


def run_migrations() -> None:
    """启动时调用,按需执行未应用的迁移。"""
    # 0. 改名兜底:把旧 mediahub.db 改成 media_manager.db
    _migrate_legacy_db_file()

    if not MIGRATIONS_DIR.exists():
        logger.warning("Migrations dir not found: %s", MIGRATIONS_DIR)
        return

    _ensure_version_table()
    applied = _applied_versions()

    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    pending = [f for f in files if f.stem not in applied]

    if not pending:
        logger.info("No pending migrations. (applied=%d)", len(applied))
        return

    logger.info("Found %d pending migrations.", len(pending))
    for f in pending:
        _apply_migration(f)
    logger.info("Migrations done.")
