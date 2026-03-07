"""Shared test fixtures."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from aligned.app import create_app
from aligned.config import Settings
from aligned.models import Base
from aligned.models.base import get_session


@pytest.fixture
def test_settings() -> Settings:
    """Settings for testing — uses in-memory SQLite."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        jwt_secret_key="test-secret",
    )


@pytest.fixture
async def db_session(test_settings: Settings) -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh in-memory database and yield a session."""
    engine = create_async_engine(test_settings.database_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def client(test_settings: Settings, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the test app."""
    app = create_app(settings=test_settings)

    # Override the session dependency
    async def _override_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = _override_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
