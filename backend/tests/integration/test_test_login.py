"""Tests for the test-login endpoint (testing-only auth bypass)."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from aligned.app import create_app
from aligned.config import Settings, get_settings


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

    async def test_route_absent_in_production(self, client: AsyncClient) -> None:
        """The regular client fixture has testing=False — route should 404."""
        response = await client.post("/api/auth/test-login", json={"email": "hacker@evil.com"})
        assert response.status_code == 404
