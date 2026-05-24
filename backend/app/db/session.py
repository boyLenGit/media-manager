"""数据库引擎与会话,SQLite 默认开启 WAL + foreign_keys。"""
from collections.abc import Iterator

from sqlalchemy.engine import Engine
from sqlalchemy.event import listens_for
from sqlmodel import Session, create_engine

from app.core.config import get_settings

_settings = get_settings()

# SQLite 多线程支持
_connect_args = {"check_same_thread": False} if _settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    _settings.database_url,
    echo=_settings.app_debug,
    connect_args=_connect_args,
)


@listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
    """SQLite 连接级别的 PRAGMA:开启 WAL、外键、增大缓存。"""
    if not _settings.database_url.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-20000")  # 20MB
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.close()


def get_session() -> Iterator[Session]:
    """FastAPI 依赖注入用,每请求一个会话。"""
    with Session(engine) as session:
        yield session
