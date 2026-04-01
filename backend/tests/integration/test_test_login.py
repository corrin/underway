"""Tests for the test-login endpoint (testing-only auth bypass)."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from underway.app import create_app
from underway.config import Settings, get_settings

TEST_DATABASE_URL = "mysql+aiomysql://underway:underway-dev-pass@localhost:3306/underway_test"


@pytest.fixture
async def testing_client(
    test_settings: Settings,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """Client with testing=True so test-login route exists."""
    settings = Settings(
        database_url=test_settings.database_url,
        jwt_secret_key=test_settings.jwt_secret_key,
        testing=True,
    )
    app = create_app(settings=settings, session_factory=db_session_factory)
    app.dependency_overrides[get_settings] = lambda: settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def production_client(
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """Client with testing=False to verify test-login route is absent."""
    settings = Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
        jwt_secret_key="test-secret-key-at-least-32-chars!",
        testing=False,
        google_client_id="fake-id",
        google_client_secret="fake-secret",
    )
    app = create_app(settings=settings, session_factory=db_session_factory)
    app.dependency_overrides[get_settings] = lambda: settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestTestLogin:
    async def test_creates_user_and_returns_token(self, testing_client: AsyncClient) -> None:
        response = await testing_client.post("/api/auth/test-login", json={"email": "playwright@test.com"})
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "playwright@test.com"

    async def test_token_works_for_auth(self, testing_client: AsyncClient) -> None:
        login_resp = await testing_client.post("/api/auth/test-login", json={"email": "auth-check@test.com"})
        token = login_resp.json()["token"]
        me_resp = await testing_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "auth-check@test.com"

    async def test_route_absent_in_production(self, production_client: AsyncClient) -> None:
        """A client with testing=False — route should 404."""
        response = await production_client.post("/api/auth/test-login", json={"email": "hacker@evil.com"})
        assert response.status_code == 404
