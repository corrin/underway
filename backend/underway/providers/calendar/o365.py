"""O365 (Microsoft) Calendar provider using Microsoft Graph API."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from underway.config import Settings
from underway.models.external_account import ExternalAccount
from underway.providers.calendar.base import CalendarProvider
from underway.providers.calendar.models import CalendarEvent, CalendarEventCreate

logger = logging.getLogger(__name__)

O365_SCOPES = [
    "https://graph.microsoft.com/Calendars.ReadWrite",
    "https://graph.microsoft.com/User.Read",
    "offline_access",
]

GRAPH_BASE = "https://graph.microsoft.com/v1.0"


class O365CalendarProvider(CalendarProvider):
    """Microsoft 365 calendar integration via the Graph API."""

    async def _get_token(
        self,
        session: AsyncSession,
        user_id: UUID,
        email: str,
    ) -> str | None:
        """Return a valid access token, refreshing if needed."""
        account = await ExternalAccount.get_by_email_provider_and_user(
            session, external_email=email, provider="o365", user_id=user_id
        )
        if not account or account.needs_reauth or not account.token:
            return None

        # Check if token might be expired (simple heuristic: refresh if last_sync older than 50 min)
        if (
            account.refresh_token
            and account.expires_at
            and account.expires_at < datetime.now(account.expires_at.tzinfo or None)
        ):
            refreshed = await _refresh_o365_token(account)
            if not refreshed:
                account.needs_reauth = True
                await session.flush()
                return None
            await session.flush()

        return account.token

    async def get_events(
        self,
        session: AsyncSession,
        user_id: UUID,
        email: str,
        start: datetime,
        end: datetime,
    ) -> list[CalendarEvent]:
        token = await self._get_token(session, user_id, email)
        if not token:
            logger.warning("No valid O365 token for %s (user %s)", email, user_id)
            return []

        headers = {"Authorization": f"Bearer {token}"}
        params = {
            "startDateTime": start.isoformat(),
            "endDateTime": end.isoformat(),
            "$orderby": "start/dateTime",
            "$top": "100",
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{GRAPH_BASE}/me/calendarView",
                headers=headers,
                params=params,
            )

        if resp.status_code != 200:
            logger.error("O365 calendar API error (%d) for %s: %s", resp.status_code, email, resp.text)
            return []

        data = resp.json()
        events: list[CalendarEvent] = []
        for item in data.get("value", []):
            start_str = item.get("start", {}).get("dateTime", "")
            end_str = item.get("end", {}).get("dateTime", "")
            if not start_str or not end_str:
                continue

            events.append(
                CalendarEvent(
                    id=item["id"],
                    title=item.get("subject", "(No title)"),
                    start=start_str,
                    end=end_str,
                    location=(item.get("location", {}) or {}).get("displayName"),
                    description=item.get("bodyPreview"),
                    provider="o365",
                )
            )

        logger.info("Retrieved %d events from O365 for %s", len(events), email)
        return events

    async def create_event(
        self,
        session: AsyncSession,
        user_id: UUID,
        email: str,
        event: CalendarEventCreate,
    ) -> CalendarEvent:
        token = await self._get_token(session, user_id, email)
        if not token:
            msg = f"No valid O365 token for {email}"
            raise RuntimeError(msg)

        body = {
            "subject": event.title,
            "start": {"dateTime": event.start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": event.end.isoformat(), "timeZone": "UTC"},
        }
        if event.location:
            body["location"] = {"displayName": event.location}
        if event.description:
            body["body"] = {"contentType": "text", "content": event.description}

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{GRAPH_BASE}/me/events", headers=headers, json=body)

        resp.raise_for_status()
        created = resp.json()
        return CalendarEvent(
            id=created["id"],
            title=created.get("subject", event.title),
            start=event.start,
            end=event.end,
            location=event.location,
            description=event.description,
            provider="o365",
        )

    async def delete_event(
        self,
        session: AsyncSession,
        user_id: UUID,
        email: str,
        event_id: str,
    ) -> bool:
        token = await self._get_token(session, user_id, email)
        if not token:
            return False

        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            resp = await client.delete(f"{GRAPH_BASE}/me/events/{event_id}", headers=headers)

        if resp.status_code in (200, 204):
            return True

        logger.error("Failed to delete O365 event %s for %s: %d", event_id, email, resp.status_code)
        return False


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------


def build_o365_oauth_url(settings: Settings) -> tuple[str, str]:
    """Return (authorization_url, state) for the O365 OAuth consent screen."""
    import secrets

    state = secrets.token_urlsafe(32)
    params = {
        "client_id": settings.o365_client_id,
        "response_type": "code",
        "redirect_uri": settings.o365_redirect_uri,
        "scope": " ".join(O365_SCOPES),
        "state": state,
        "prompt": "consent",
    }
    base = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    qs = "&".join(f"{k}={httpx.URL('', params={k: v}).params[k]}" for k, v in params.items())
    return f"{base}?{qs}", state


async def handle_o365_oauth_callback(
    code: str,
    state: str,
    settings: Settings,
    session: AsyncSession,
    user_id: UUID,
) -> str:
    """Exchange the authorization code for tokens, store them, return the email."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.o365_redirect_uri,
                "client_id": settings.o365_client_id,
                "client_secret": settings.o365_client_secret,
                "scope": " ".join(O365_SCOPES),
            },
        )
    resp.raise_for_status()
    token_data = resp.json()

    access_token = token_data["access_token"]
    refresh_token = token_data.get("refresh_token")

    # Get user email from Graph API
    async with httpx.AsyncClient() as client:
        me_resp = await client.get(
            f"{GRAPH_BASE}/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    me_resp.raise_for_status()
    o365_email: str = me_resp.json().get("mail") or me_resp.json()["userPrincipalName"]

    # Store or update account
    account = await ExternalAccount.get_by_email_provider_and_user(
        session, external_email=o365_email, provider="o365", user_id=user_id
    )

    cred_data = {
        "token": access_token,
        "refresh_token": refresh_token,
        "token_uri": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "client_id": settings.o365_client_id,
        "client_secret": settings.o365_client_secret,
        "scopes": " ".join(O365_SCOPES),
    }

    if account:
        for key, value in cred_data.items():
            setattr(account, key, value)
        account.needs_reauth = False
        account.use_for_calendar = True
    else:
        primary = await ExternalAccount.get_primary_account(session, user_id, "calendar")
        account = ExternalAccount(
            user_id=user_id,
            external_email=o365_email,
            provider="o365",
            use_for_calendar=True,
            is_primary_calendar=primary is None,
            **cred_data,
        )
        session.add(account)

    await session.flush()
    logger.info("Stored O365 credentials for %s (user %s)", o365_email, user_id)
    return o365_email


async def _refresh_o365_token(account: ExternalAccount) -> bool:
    """Refresh an O365 token using the refresh token. Updates account in-place."""
    if not account.refresh_token:
        return False

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": account.refresh_token,
                "client_id": account.client_id or "",
                "client_secret": account.client_secret or "",
                "scope": account.scopes or "",
            },
        )

    if resp.status_code != 200:
        logger.error("O365 token refresh failed for %s: %s", account.external_email, resp.text)
        return False

    data = resp.json()
    account.token = data["access_token"]
    if "refresh_token" in data:
        account.refresh_token = data["refresh_token"]
    return True
