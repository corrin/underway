"""Integration tests for Todoist account management routes."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from underway.auth.jwt import create_access_token
from underway.models.external_account import ExternalAccount
from underway.models.user import User

SECRET = "test-secret-key-at-least-32-chars!"


async def _create_user(db_session: AsyncSession) -> User:
    user = User(app_login="todoist-user@example.com")
    user.id = uuid.uuid4()
    db_session.add(user)
    await db_session.commit()
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.app_login, SECRET)
    return {"Authorization": f"Bearer {token}"}


class TestAddAccount:
    async def test_add_todoist_account(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post(
            "/api/todoist/add-account",
            json={"todoist_email": "me@todoist.com", "api_key": "test-key"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    async def test_add_duplicate_returns_409(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        account = ExternalAccount(
            user_id=user.id,
            external_email="dup@todoist.com",
            provider="todoist",
            api_key="key",
            use_for_tasks=True,
        )
        db_session.add(account)
        await db_session.commit()

        response = await client.post(
            "/api/todoist/add-account",
            json={"todoist_email": "dup@todoist.com", "api_key": "key2"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 409

    async def test_add_missing_fields_returns_400(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post(
            "/api/todoist/add-account",
            json={"todoist_email": "me@todoist.com"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 400

    async def test_add_returns_401_without_token(self, client: AsyncClient) -> None:
        response = await client.post(
            "/api/todoist/add-account",
            json={"todoist_email": "me@todoist.com", "api_key": "key"},
        )
        assert response.status_code == 401


class TestUpdateKey:
    async def test_update_key(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        account = ExternalAccount(
            user_id=user.id,
            external_email="upd@todoist.com",
            provider="todoist",
            api_key="old-key",
            use_for_tasks=True,
        )
        db_session.add(account)
        await db_session.commit()

        response = await client.post(
            "/api/todoist/update-key",
            json={"todoist_email": "upd@todoist.com", "api_key": "new-key"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200

    async def test_update_nonexistent_returns_404(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post(
            "/api/todoist/update-key",
            json={"todoist_email": "nope@todoist.com", "api_key": "key"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 404


class TestDeleteAccount:
    async def test_delete_account(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        account = ExternalAccount(
            user_id=user.id,
            external_email="del@todoist.com",
            provider="todoist",
            api_key="key",
            use_for_tasks=True,
        )
        db_session.add(account)
        await db_session.commit()

        response = await client.post(
            "/api/todoist/delete-account",
            json={"todoist_email": "del@todoist.com"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200

    async def test_delete_nonexistent_returns_404(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post(
            "/api/todoist/delete-account",
            json={"todoist_email": "nope@todoist.com"},
            headers=_auth_headers(user),
        )
        assert response.status_code == 404


class TestTestConnection:
    async def test_missing_key_returns_failure(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post(
            "/api/todoist/test",
            json={},
            headers=_auth_headers(user),
        )
        assert response.status_code == 200
        assert response.json()["success"] is False
