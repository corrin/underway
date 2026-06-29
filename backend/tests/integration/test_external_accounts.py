"""Integration tests for the external-accounts task-enablement action."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from underway.auth.jwt import create_access_token
from underway.models.external_account import ExternalAccount
from underway.models.user import User

SECRET = "test-secret-key-at-least-32-chars!"


async def _create_user(db_session: AsyncSession, email: str = "acct@example.com") -> User:
    user = User(app_login=email)
    user.id = uuid.uuid4()
    db_session.add(user)
    await db_session.commit()
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.app_login, SECRET)
    return {"Authorization": f"Bearer {token}"}


async def _create_account(db_session: AsyncSession, user: User, provider: str = "google") -> ExternalAccount:
    account = ExternalAccount(
        user_id=user.id,
        external_email=user.app_login,
        provider=provider,
        token="tok",
        use_for_calendar=True,
        use_for_tasks=False,
    )
    db_session.add(account)
    await db_session.commit()
    await db_session.refresh(account)
    return account


class TestUseForTasks:
    async def test_enables_use_for_tasks(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        account = await _create_account(db_session, user)

        response = await client.post(
            f"/api/external-accounts/{account.id}/use-for-tasks",
            headers=_auth_headers(user),
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        # Verify via the API (the request commits in its own session, separate from db_session).
        listed = await client.get("/api/external-accounts", headers=_auth_headers(user))
        accounts = listed.json()
        assert len(accounts) == 1
        assert accounts[0]["use_for_tasks"] is True
        assert accounts[0]["is_primary_tasks"] is True

    async def test_other_users_account_returns_404(self, client: AsyncClient, db_session: AsyncSession) -> None:
        owner = await _create_user(db_session, "owner@example.com")
        intruder = await _create_user(db_session, "intruder@example.com")
        account = await _create_account(db_session, owner)

        response = await client.post(
            f"/api/external-accounts/{account.id}/use-for-tasks",
            headers=_auth_headers(intruder),
        )
        assert response.status_code == 404

    async def test_invalid_id_returns_400(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        response = await client.post(
            "/api/external-accounts/not-a-uuid/use-for-tasks",
            headers=_auth_headers(user),
        )
        assert response.status_code == 400
