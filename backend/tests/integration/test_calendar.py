"""Integration tests for calendar API routes."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from underway.auth.jwt import create_access_token
from underway.models.external_account import ExternalAccount
from underway.models.user import User
from underway.providers.calendar.models import CalendarEvent

SECRET = "test-secret-key-at-least-32-chars!"


async def _create_user(session: AsyncSession, email: str = "cal@test.com") -> User:
    user = User(app_login=email)
    user.id = uuid.uuid4()
    session.add(user)
    await session.flush()
    return user


async def _create_calendar_account(
    session: AsyncSession,
    user: User,
    provider: str = "google",
    email: str = "cal@gmail.com",
    primary: bool = True,
) -> ExternalAccount:
    account = ExternalAccount(
        user_id=user.id,
        external_email=email,
        provider=provider,
        token="test-token",
        refresh_token="test-refresh",
        token_uri="https://oauth2.googleapis.com/token",
        client_id="test-client-id",
        client_secret="test-secret",
        scopes="openid calendar",
        use_for_calendar=True,
        is_primary_calendar=primary,
    )
    session.add(account)
    await session.flush()
    return account


def _auth_headers(user: User) -> dict[str, str]:
    token = create_access_token(user.id, user.app_login, SECRET)
    return {"Authorization": f"Bearer {token}"}


class TestListEvents:
    async def test_no_calendar_returns_empty(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await db_session.commit()

        resp = await client.get("/api/calendar/events", headers=_auth_headers(user))
        assert resp.status_code == 200
        data = resp.json()
        assert data["events"] == []
        assert "No calendar connected" in data.get("message", "")

    @patch("underway.routes.calendar.get_calendar_provider")
    async def test_returns_events_from_provider(
        self, mock_factory: AsyncMock, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        user = await _create_user(db_session)
        await _create_calendar_account(db_session, user)
        await db_session.commit()

        now = datetime.now(UTC)
        mock_provider = AsyncMock()
        mock_provider.get_events.return_value = [
            CalendarEvent(
                id="evt-1",
                title="Test Meeting",
                start=now,
                end=now + timedelta(hours=1),
                provider="google",
            )
        ]
        mock_factory.return_value = mock_provider

        resp = await client.get("/api/calendar/events", headers=_auth_headers(user))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["events"]) == 1
        assert data["events"][0]["title"] == "Test Meeting"

    async def test_unauthenticated_returns_401(self, client: AsyncClient) -> None:
        resp = await client.get("/api/calendar/events")
        assert resp.status_code in (401, 403)


class TestCreateEvent:
    @patch("underway.routes.calendar.get_calendar_provider")
    async def test_create_event_success(
        self, mock_factory: AsyncMock, client: AsyncClient, db_session: AsyncSession
    ) -> None:
        user = await _create_user(db_session)
        await _create_calendar_account(db_session, user)
        await db_session.commit()

        now = datetime.now(UTC)
        mock_provider = AsyncMock()
        mock_provider.create_event.return_value = CalendarEvent(
            id="new-evt",
            title="New Event",
            start=now,
            end=now + timedelta(hours=1),
            provider="google",
        )
        mock_factory.return_value = mock_provider

        resp = await client.post(
            "/api/calendar/create-event",
            json={
                "title": "New Event",
                "start": now.isoformat(),
                "end": (now + timedelta(hours=1)).isoformat(),
            },
            headers=_auth_headers(user),
        )
        assert resp.status_code == 200
        assert resp.json()["event"]["title"] == "New Event"

    async def test_create_event_no_calendar_returns_400(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await db_session.commit()

        now = datetime.now(UTC)
        resp = await client.post(
            "/api/calendar/create-event",
            json={
                "title": "Event",
                "start": now.isoformat(),
                "end": (now + timedelta(hours=1)).isoformat(),
            },
            headers=_auth_headers(user),
        )
        assert resp.status_code == 400


class TestDeleteEvent:
    async def test_delete_no_calendar_returns_400(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await db_session.commit()

        resp = await client.delete(
            "/api/calendar/delete-event?event_id=evt-1",
            headers=_auth_headers(user),
        )
        assert resp.status_code == 400

    async def test_delete_missing_event_id_returns_400(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await _create_calendar_account(db_session, user)
        await db_session.commit()

        resp = await client.delete(
            "/api/calendar/delete-event",
            headers=_auth_headers(user),
        )
        assert resp.status_code == 400


class TestSetPrimary:
    async def test_set_primary_success(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        account = await _create_calendar_account(db_session, user, primary=False)
        await db_session.commit()

        resp = await client.post(
            "/api/calendar/set-primary",
            json={"account_id": str(account.id)},
            headers=_auth_headers(user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    async def test_set_primary_invalid_id_returns_400(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await db_session.commit()

        resp = await client.post(
            "/api/calendar/set-primary",
            json={"account_id": "not-a-uuid"},
            headers=_auth_headers(user),
        )
        assert resp.status_code == 400

    async def test_set_primary_not_found_returns_404(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await db_session.commit()

        resp = await client.post(
            "/api/calendar/set-primary",
            json={"account_id": str(uuid.uuid4())},
            headers=_auth_headers(user),
        )
        assert resp.status_code == 404


class TestOAuthInitiate:
    async def test_google_initiate_no_config_returns_400(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await db_session.commit()

        resp = await client.post("/api/oauth/google/initiate", headers=_auth_headers(user))
        # google_client_id is empty in test settings, so should fail
        assert resp.status_code == 400

    async def test_o365_initiate_no_config_returns_400(self, client: AsyncClient, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await db_session.commit()

        resp = await client.post("/api/oauth/o365/initiate", headers=_auth_headers(user))
        assert resp.status_code == 400

    async def test_google_callback_missing_params_returns_400(self, client: AsyncClient) -> None:
        resp = await client.get("/api/oauth/google/callback")
        assert resp.status_code == 400

    async def test_o365_callback_missing_params_returns_400(self, client: AsyncClient) -> None:
        resp = await client.get("/api/oauth/o365/callback")
        assert resp.status_code == 400

    async def test_google_callback_invalid_state_returns_400(self, client: AsyncClient) -> None:
        resp = await client.get("/api/oauth/google/callback?code=test&state=invalid")
        assert resp.status_code == 400

    async def test_o365_callback_invalid_state_returns_400(self, client: AsyncClient) -> None:
        resp = await client.get("/api/oauth/o365/callback?code=test&state=invalid")
        assert resp.status_code == 400
