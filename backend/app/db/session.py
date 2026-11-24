import asyncio
from collections.abc import AsyncIterator
from typing import Any

from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.base import Base


def create_engine_and_sessionmaker(
    database_url: str,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create an async SQLAlchemy engine and session maker for SQLite or PostgreSQL."""
    engine_kwargs: dict[str, Any] = {"future": True}
    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in database_url:
            engine_kwargs["poolclass"] = StaticPool
    else:
        engine_kwargs["pool_pre_ping"] = True

    engine = create_async_engine(database_url, **engine_kwargs)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    return engine, session_factory


async def init_db(engine: AsyncEngine) -> None:
    """Ensure all ORM tables are registered and created."""
    import app.db.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ensure_db_initialized(app: FastAPI) -> None:
    """Lazily initialize database schema once per app instance (safe with ASGITransport)."""
    if getattr(app.state, "db_initialized", False):
        return

    lock: asyncio.Lock = app.state.db_init_lock
    async with lock:
        if getattr(app.state, "db_initialized", False):
            return
        await init_db(app.state.engine)
        app.state.db_initialized = True


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding an initialized async SQLAlchemy session."""
    await ensure_db_initialized(request.app)
    session_factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with session_factory() as session:
        yield session
