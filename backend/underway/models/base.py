"""SQLAlchemy async base and session management."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from underway.config import get_settings


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""


_engine = None
_session_factory = None


def init_db(database_url: str | None = None) -> None:
    """Initialize the async engine and session factory."""
    global _engine, _session_factory
    url = database_url or get_settings().database_url
    _engine = create_async_engine(url, echo=False)
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session (for use as a FastAPI dependency)."""
    if _session_factory is None:
        init_db()
    assert _session_factory is not None
    async with _session_factory() as session:
        yield session
