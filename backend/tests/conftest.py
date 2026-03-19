"""Shared test fixtures."""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Load env from the backend .env file BEFORE importing app code that reads settings.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from underway.app import create_app  # noqa: E402
from underway.config import Settings, get_settings  # noqa: E402
from underway.models import Base  # noqa: E402

# CI sets TEST_DATABASE_URL directly; locally we derive it from DATABASE_URL.
_explicit_test_url = os.environ.get("TEST_DATABASE_URL")
if _explicit_test_url:
    TEST_DATABASE_URL = _explicit_test_url
else:
    _db_url_str = os.environ.get("DATABASE_URL")
    if not _db_url_str:
        pytest.exit("Set DATABASE_URL or TEST_DATABASE_URL — cannot find test database", returncode=1)

    _parsed = make_url(_db_url_str)
    _db_name = _parsed.database
    if not _db_name:
        pytest.exit("DATABASE_URL has no database name", returncode=1)
    if _db_name.endswith("_test"):
        pytest.exit(f"DATABASE_URL database '{_db_name}' already ends with _test", returncode=1)

    _test_db_name = _db_name.rsplit("_", 1)[0] + "_test"
    TEST_DATABASE_URL = _parsed.set(database=_test_db_name).render_as_string(hide_password=False)


@pytest.fixture
def test_settings() -> Settings:
    """Settings for testing — uses MariaDB test database."""
    return Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        jwt_secret_key="test-secret-key-at-least-32-chars!",
        base_url="http://localhost:8000",
        testing=True,
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
