"""Integration tests for settings routes."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from aligned.auth.jwt import create_access_token
from aligned.models.user import User

SECRET = "test-secret-key-at-least-32-chars!"


async def _create_authed_user(db_session: AsyncSession) -> tuple[User, str]:
    """Helper: create a user and return (user, jwt_token)."""
    user = User(app_login="settings@example.com")
    user.id = uuid.uuid4()
    user.llm_model = "claude-sonnet-4-20250514"
    user.schedule_slot_duration = 60
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(user.id, user.app_login, SECRET)
    return user, token


class TestGetSettings:
    async def test_returns_settings(self, client: AsyncClient, db_session: AsyncSession) -> None:
        _, token = await _create_authed_user(db_session)
        response = await client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200
        data = response.json()
        assert data["llm_model"] == "claude-sonnet-4-20250514"
        assert data["schedule_slot_duration"] == 60
        assert data["ai_api_key"] is None

    async def test_returns_401_without_token(self, client: AsyncClient) -> None:
        response = await client.get("/api/settings")
        assert response.status_code == 401


class TestUpdateSettings:
    async def test_update_llm_model(self, client: AsyncClient, db_session: AsyncSession) -> None:
        _, token = await _create_authed_user(db_session)
        response = await client.put(
            "/api/settings",
            json={"llm_model": "gpt-4o"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["llm_model"] == "gpt-4o"

    async def test_update_slot_duration(self, client: AsyncClient, db_session: AsyncSession) -> None:
        _, token = await _create_authed_user(db_session)
        response = await client.put(
            "/api/settings",
            json={"schedule_slot_duration": 30},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["schedule_slot_duration"] == 30

    async def test_invalid_slot_duration_returns_422(self, client: AsyncClient, db_session: AsyncSession) -> None:
        _, token = await _create_authed_user(db_session)
        response = await client.put(
            "/api/settings",
            json={"schedule_slot_duration": 45},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 422

    async def test_update_multiple_fields(self, client: AsyncClient, db_session: AsyncSession) -> None:
        _, token = await _create_authed_user(db_session)
        response = await client.put(
            "/api/settings",
            json={"llm_model": "gpt-4o", "ai_instructions": "Be concise"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["llm_model"] == "gpt-4o"
        assert data["ai_instructions"] == "Be concise"

    async def test_returns_401_without_token(self, client: AsyncClient) -> None:
        response = await client.put("/api/settings", json={"llm_model": "test"})
        assert response.status_code == 401
