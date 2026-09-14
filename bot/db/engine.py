import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from bot.db.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(db_path: str) -> AsyncEngine:
    global _engine, _session_factory
    if _engine is None:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        _engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def init_models(db_path: str) -> None:
    engine = get_engine(db_path)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope() -> AsyncIterator[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Call init_models() before using session_scope()")
    async with _session_factory() as session:
        yield session
