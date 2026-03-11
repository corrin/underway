"""Shared test fixtures."""

import os
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from underway.app import create_app
from underway.config import Settings, get_settings
from underway.models import Base

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "mysql+aiomysql://underway:underway-dev-pass@localhost:3306/underway_test",
)


@pytest.fixture
def test_settings() -> Settings:
    """Settings for testing — uses MariaDB test database."""
    return Settings(
        database_url=TEST_DATABASE_URL,
        jwt_secret_key="test-secret-key-at-least-32-chars!",
    )


@pytest.fixture
async def db_engine() -> AsyncGenerator[object, None]:
    """Shared engine: create tables before tests, drop after."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def db_session_factory(db_engine: object) -> async_sessionmaker[AsyncSession]:
    """Session factory bound to the shared test engine."""
    from sqlalchemy.ext.asyncio import AsyncEngine

    assert isinstance(db_engine, AsyncEngine)
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest.fixture
async def db_session(db_session_factory: async_sessionmaker[AsyncSession]) -> AsyncGenerator[AsyncSession, None]:
    """Yield a session for direct DB access in tests."""
    async with db_session_factory() as session:
        yield session


@pytest.fixture
async def client(
    test_settings: Settings,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP client wired to the test app with shared session factory."""
    app = create_app(settings=test_settings, session_factory=db_session_factory)

    # Override get_settings so Depends(get_settings) returns test_settings
    app.dependency_overrides[get_settings] = lambda: test_settings

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
