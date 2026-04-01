"""Background token refresh for OAuth providers (Google, O365)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from underway.config import Settings, get_settings
from underway.models.external_account import ExternalAccount

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 30 * 60  # 30 minutes
REFRESH_AHEAD_MINUTES = 15  # refresh tokens expiring within this window


async def refresh_soon_expiring_tokens(
    session: AsyncSession,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Find accounts with tokens expiring soon and refresh them."""
    cutoff = datetime.now(UTC) + timedelta(minutes=REFRESH_AHEAD_MINUTES)

    result = await session.execute(
        select(ExternalAccount).where(
            ExternalAccount.needs_reauth.is_(False),
            ExternalAccount.refresh_token.is_not(None),
            ExternalAccount.provider.in_(["google", "o365"]),
            or_(
                ExternalAccount.expires_at.is_(None),
                ExternalAccount.expires_at < cutoff,
            ),
        )
    )
    accounts = list(result.scalars().all())

    if not accounts:
        logger.info("No accounts need token refresh")
        return {"success": 0, "failed": 0}

    logger.info("Found %d accounts for token refresh", len(accounts))
    success = 0
    failed = 0

    cfg = settings or get_settings()
    for account in accounts:
        try:
            await _refresh_account_token(session, account, cfg)
            success += 1
        except Exception:
            logger.exception("Failed to refresh token for %s", account.external_email)
            account.needs_reauth = True
            failed += 1

    await session.flush()
    logger.info("Token refresh: %d success, %d failed", success, failed)
    return {"success": success, "failed": failed}


async def _refresh_account_token(
    session: AsyncSession,
    account: ExternalAccount,
    settings: Settings,
) -> None:
    """Refresh the OAuth token for a single account."""
    if account.provider not in ("google", "o365"):
        raise ValueError(f"Unsupported provider for token refresh: {account.provider}")

    if account.provider == "google":
        creds = Credentials(
            token=account.token,
            refresh_token=account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
        )
        await asyncio.to_thread(creds.refresh, Request())
        account.token = creds.token
        if creds.expiry:
            account.expires_at = creds.expiry.replace(tzinfo=UTC)
        account.last_sync = datetime.now(UTC)
        logger.info("Refreshed Google token for %s", account.external_email)
        return

    # provider == "o365"
    import httpx

    resp = await httpx.AsyncClient().post(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": account.refresh_token,
            "client_id": settings.o365_client_id,
            "client_secret": settings.o365_client_secret,
            "scope": account.scopes or "",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    account.token = data["access_token"]
    if "refresh_token" in data:
        account.refresh_token = data["refresh_token"]
    if "expires_in" in data:
        account.expires_at = datetime.now(UTC) + timedelta(seconds=data["expires_in"])
    account.last_sync = datetime.now(UTC)
    logger.info("Refreshed O365 token for %s", account.external_email)


async def token_refresh_loop(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings | None = None,
) -> None:
    """Background loop that refreshes tokens every 30 minutes."""
    cfg = settings or get_settings()
    logger.info("Starting token refresh background loop")
    while True:
        try:
            async with session_factory() as session:
                await refresh_soon_expiring_tokens(session, cfg)
                await session.commit()
        except Exception:
            logger.exception("Error in token refresh loop")
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
