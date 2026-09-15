import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]

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


async def init_database(db_path: str) -> None:
    """Apply migrations and open the connection pool."""
    global _engine, _session_factory
    Path(db_path).resolve().parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(command.upgrade, alembic_config(db_path), "head")

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
