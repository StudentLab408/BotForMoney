import asyncio
import datetime as dt
import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, closing
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def alembic_config(db_path: str) -> AlembicConfig:
    config = AlembicConfig(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return config


def _set_sqlite_pragmas(dbapi_connection, _record) -> None:
    cursor = dbapi_connection.cursor()
    # WAL lets reads continue during writes; busy_timeout waits for a lock instead of failing at once.
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _move_aside_unmigrated_database(db_path: str) -> None:
    """A file with tables but no applied migration was made without Alembic; migrating it would fail.

    It is renamed, never deleted, and the bot starts with a fresh database.
    """
    path = Path(db_path)
    if not path.exists():
        return
    with closing(sqlite3.connect(path)) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        applied = "alembic_version" in tables and conn.execute("SELECT 1 FROM alembic_version").fetchone()
    if applied or not {t for t in tables if t != "alembic_version" and not t.startswith("sqlite_")}:
        return

    target = path.with_name(f"{path.stem}.pre-migrations-{dt.datetime.now():%Y%m%d-%H%M%S}{path.suffix}")
    path.rename(target)
    for suffix in ("-wal", "-shm"):
        sidecar = Path(f"{path}{suffix}")
        if sidecar.exists():
            sidecar.rename(Path(f"{target}{suffix}"))
    logger.warning("Database %s was created without migrations; moved it to %s and starting fresh", path, target)


def _migrate(db_path: str) -> None:
    _move_aside_unmigrated_database(db_path)
    command.upgrade(alembic_config(db_path), "head")


async def init_database(db_path: str) -> None:
    """Apply migrations and open the connection pool."""
    global _engine, _session_factory
    Path(db_path).resolve().parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(_migrate, db_path)

    if _engine is None:
        _engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        event.listen(_engine.sync_engine, "connect", _set_sqlite_pragmas)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def dispose_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Call init_database() before using session_scope()")
    async with _session_factory() as session:
        yield session
