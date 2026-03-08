"""Integration tests for auth routes."""

import uuid
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from aligned.auth.jwt import create_access_token
from aligned.models.user import User

SECRET = "test-secret-key-at-least-32-chars!"


class TestGoogleLogin:
    @patch("aligned.routes.auth.verify_google_id_token")
    async def test_login_creates_user(self, mock_verify: object, client: AsyncClient) -> None:
        mock_verify.return_value = "new@example.com"  # type: ignore[union-attr]
        response = await client.post("/api/auth/google", json={"id_token": "valid-google-token"})
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["user"]["email"] == "new@example.com"

    @patch("aligned.routes.auth.verify_google_id_token")
    async def test_login_returns_existing_user(
        self, mock_verify: object, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        user = User(app_login="existing@example.com")
        user.id = uuid.uuid4()
        db_session.add(user)
        await db_session.commit()

        mock_verify.return_value = "existing@example.com"  # type: ignore[union-attr]
        response = await client.post("/api/auth/google", json={"id_token": "valid-token"})
        assert response.status_code == 200
        assert response.json()["user"]["email"] == "existing@example.com"
        assert response.json()["user"]["id"] == str(user.id)

    @patch("aligned.routes.auth.verify_google_id_token")
    async def test_login_invalid_token_returns_401(self, mock_verify: object, client: AsyncClient) -> None:
        mock_verify.side_effect = ValueError("bad token")  # type: ignore[union-attr]
        response = await client.post("/api/auth/google", json={"id_token": "bad-token"})
        assert response.status_code == 401


class TestGetMe:
    async def test_returns_user_profile(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = User(app_login="me@example.com")
        user.id = uuid.uuid4()
        user.llm_model = "claude-sonnet-4-20250514"
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, user.app_login, SECRET)
        response = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@example.com"
        assert data["llm_model"] == "claude-sonnet-4-20250514"

    async def test_returns_401_without_token(self, client: AsyncClient) -> None:
        response = await client.get("/api/auth/me")
        assert response.status_code == 401

    async def test_returns_401_with_invalid_token(self, client: AsyncClient) -> None:
        response = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid"})
        assert response.status_code == 401


class TestLogout:
    async def test_logout_returns_success(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = User(app_login="logout@example.com")
        user.id = uuid.uuid4()
        db_session.add(user)
        await db_session.commit()

        token = create_access_token(user.id, user.app_login, SECRET)
        response = await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
