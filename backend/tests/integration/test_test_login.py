"""Tests for the test-login endpoint (testing-only auth bypass)."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from underway.app import create_app
from underway.config import Settings, get_settings


@pytest.fixture
async def production_client(
    test_settings: Settings,
    db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncClient, None]:
    """Client with testing=False and all required settings for validate_required()."""
    settings = Settings(
        _env_file=None,
        database_password=test_settings.database_password,
        database_name=test_settings.database_name,
        jwt_secret_key=test_settings.jwt_secret_key,
        base_url=test_settings.base_url,
        testing=False,
        google_client_id="fake-google-id",
        google_client_secret="fake-google-secret",
        todoist_client_id="fake-todoist-id",
        todoist_client_secret="fake-todoist-secret",
    )
    app = create_app(settings=settings, session_factory=db_session_factory)
    app.dependency_overrides[get_settings] = lambda: settings
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestTestLogin:
    async def test_creates_user_and_returns_token(self, client: AsyncClient) -> None:
        response = await client.post("/api/auth/test-login", json={"email": "playwright@test.com"})
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "playwright@test.com"

    async def test_token_works_for_auth(self, client: AsyncClient) -> None:
        login_resp = await client.post("/api/auth/test-login", json={"email": "auth-check@test.com"})
        token = login_resp.json()["token"]
        me_resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == "auth-check@test.com"

    async def test_route_absent_in_production(self, production_client: AsyncClient) -> None:
        """Production client has testing=False — route should 404."""
        response = await production_client.post("/api/auth/test-login", json={"email": "hacker@evil.com"})
        assert response.status_code == 404
