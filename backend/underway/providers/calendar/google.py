"""Google Calendar provider using the Google Calendar API."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from googleapiclient._apis.calendar.v3.schemas import Event, EventDateTime

from google.auth.transport.requests import AuthorizedSession, Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import AsyncSession

from underway.config import get_settings

from underway.config import Settings
from underway.models.external_account import ExternalAccount
from underway.providers.calendar.base import CalendarProvider
from underway.providers.calendar.models import CalendarEvent, CalendarEventCreate

logger = logging.getLogger(__name__)

GOOGLE_CALENDAR_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/userinfo.email",
]


class GoogleCalendarProvider(CalendarProvider):
    """Google Calendar integration via the Calendar API v3."""

    async def _get_credentials(
        self,
        session: AsyncSession,
        user_id: UUID,
        email: str,
    ) -> Credentials | None:
        """Build Google credentials from the stored ExternalAccount, refreshing if needed."""
        account = await ExternalAccount.get_by_email_provider_and_user(
            session, external_email=email, provider="google", user_id=user_id
        )
        if not account or account.needs_reauth:
            return None

        creds = Credentials(
            token=account.token,
            refresh_token=account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=get_settings().google_client_id,
            client_secret=get_settings().google_client_secret,
        )
        if creds.expired and creds.refresh_token:
            await asyncio.to_thread(creds.refresh, Request())
            account.token = creds.token
            if creds.expiry:
                account.expires_at = creds.expiry.replace(tzinfo=UTC)
            await session.flush()

        return creds

    async def get_events(
        self,
        session: AsyncSession,
        user_id: UUID,
        email: str,
        start: datetime,
        end: datetime,
    ) -> list[CalendarEvent]:
        creds = await self._get_credentials(session, user_id, email)
        if not creds:
            logger.warning("No valid Google credentials for %s (user %s)", email, user_id)
            return []

        service = await asyncio.to_thread(build, "calendar", "v3", credentials=creds)
        try:
            def _list_events() -> dict:  # type: ignore[type-arg]
                return (
                    service.events()
                    .list(
                        calendarId="primary",
                        timeMin=start.isoformat(),
                        timeMax=end.isoformat(),
                        singleEvents=True,
                        orderBy="startTime",
                    )
                    .execute()
                )
            result = await asyncio.to_thread(_list_events)
        except HttpError as exc:
            logger.error("Google Calendar API error for %s: %s", email, exc)
            account = await ExternalAccount.get_by_email_provider_and_user(
                session, external_email=email, provider="google", user_id=user_id
            )
            if account:
                account.needs_reauth = True
                await session.flush()
            return []

        events: list[CalendarEvent] = []
        for item in result.get("items", []):
            start_raw = item.get("start", {})
            end_raw = item.get("end", {})
            start_str = start_raw.get("dateTime") or start_raw.get("date")
            end_str = end_raw.get("dateTime") or end_raw.get("date")
            if not start_str or not end_str:
                continue

            events.append(
                CalendarEvent(
                    id=item["id"],
                    title=item.get("summary", "(No title)"),
                    start=start_str,
                    end=end_str,
                    location=item.get("location"),
                    description=item.get("description"),
                    provider="google",
                )
            )

        logger.info("Retrieved %d events from Google Calendar for %s", len(events), email)
        return events

    async def create_event(
        self,
        session: AsyncSession,
        user_id: UUID,
        email: str,
        event: CalendarEventCreate,
    ) -> CalendarEvent:
        creds = await self._get_credentials(session, user_id, email)
        if not creds:
            msg = f"No valid Google credentials for {email}"
            raise RuntimeError(msg)

        service = await asyncio.to_thread(build, "calendar", "v3", credentials=creds)
        start_dt: EventDateTime = {"dateTime": event.start.isoformat(), "timeZone": "UTC"}
        end_dt: EventDateTime = {"dateTime": event.end.isoformat(), "timeZone": "UTC"}
        body: Event = {
            "summary": event.title,
            "start": start_dt,
            "end": end_dt,
        }
        if event.location:
            body["location"] = event.location
        if event.description:
            body["description"] = event.description

        created = await asyncio.to_thread(lambda: service.events().insert(calendarId="primary", body=body).execute())
        return CalendarEvent(
            id=created["id"],
            title=created.get("summary", event.title),
            start=event.start,
            end=event.end,
            location=event.location,
            description=event.description,
            provider="google",
        )

    async def delete_event(
        self,
        session: AsyncSession,
        user_id: UUID,
        email: str,
        event_id: str,
    ) -> bool:
        creds = await self._get_credentials(session, user_id, email)
        if not creds:
            return False

        service = await asyncio.to_thread(build, "calendar", "v3", credentials=creds)
        try:
            await asyncio.to_thread(lambda: service.events().delete(calendarId="primary", eventId=event_id).execute())
        except HttpError:
            logger.exception("Failed to delete Google event %s for %s", event_id, email)
            return False
        return True


# ---------------------------------------------------------------------------
# OAuth helpers (used by the OAuth routes, not the provider interface)
# ---------------------------------------------------------------------------


def _make_google_flow(settings: Settings, *, autogenerate_code_verifier: bool = False) -> Flow:
    """Build a Google OAuth Flow from app settings.

    Pass autogenerate_code_verifier=True when building the initiation flow so
    PKCE is explicitly enabled.  Leave it False for the callback reconstruction
    (the verifier is re-injected from the DB instead).
    """
    return Flow.from_client_config(
        {
            "web": {
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uris": [settings.google_redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=GOOGLE_CALENDAR_SCOPES,
        redirect_uri=settings.google_redirect_uri,
        autogenerate_code_verifier=autogenerate_code_verifier,
    )


def build_google_oauth_url(settings: Settings) -> tuple[str, str, str | None]:
    """Return (authorization_url, state, code_verifier) for the Google OAuth consent screen.

    The code_verifier must be persisted by the caller (e.g. in the DB) and
    passed back into handle_google_oauth_callback to complete the PKCE exchange.
    It may be None if the installed flow version does not use PKCE.
    """
    # autogenerate_code_verifier=True is the default in from_client_config but
    # we pass it explicitly so the intent is clear and not sensitive to library defaults.
    flow = _make_google_flow(settings, autogenerate_code_verifier=True)
    authorization_url, state = flow.authorization_url(
        prompt="consent",
        access_type="offline",
    )
    # flow.code_verifier is set by authorization_url() when autogenerate_code_verifier=True
    code_verifier: str | None = flow.code_verifier or None
    return authorization_url, state, code_verifier


async def handle_google_oauth_callback(
    code: str,
    session: AsyncSession,
    user_id: UUID,
    settings: Settings,
    code_verifier: str | None = None,
) -> str:
    """Exchange the authorization code for tokens, store them, return the calendar email."""
    flow = _make_google_flow(settings)
    if code_verifier:
        # Re-inject the PKCE code_verifier so flow.fetch_token sends it in the token exchange
        flow.code_verifier = code_verifier
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Retrieve the Google email associated with these credentials
    authed_session = AuthorizedSession(creds)
    resp = authed_session.get("https://openidconnect.googleapis.com/v1/userinfo")
    resp.raise_for_status()
    google_email: str = resp.json()["email"]

    # Store or update ExternalAccount
    account = await ExternalAccount.get_by_email_provider_and_user(
        session, external_email=google_email, provider="google", user_id=user_id
    )

    cred_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "scopes": " ".join(creds.scopes) if creds.scopes else "",
        "expires_at": creds.expiry.replace(tzinfo=UTC) if creds.expiry else None,
    }

    if account:
        for key, value in cred_data.items():
            setattr(account, key, value)
        account.needs_reauth = False
        account.use_for_calendar = True
    else:
        # Check if this is the first calendar account (make it primary)
        primary = await ExternalAccount.get_primary_account(session, user_id, "calendar")
        account = ExternalAccount(
            user_id=user_id,
            external_email=google_email,
            provider="google",
            use_for_calendar=True,
            is_primary_calendar=primary is None,
            **cred_data,
        )
        session.add(account)

    await session.flush()
    logger.info("Stored Google Calendar credentials for %s (user %s)", google_email, user_id)
    return google_email
