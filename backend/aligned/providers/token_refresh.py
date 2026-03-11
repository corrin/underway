"""Background token refresh for OAuth providers (Google, O365)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from aligned.models.external_account import ExternalAccount

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

REFRESH_INTERVAL_SECONDS = 30 * 60  # 30 minutes
TOKEN_AGE_CUTOFF_MINUTES = 45


async def refresh_soon_expiring_tokens(
    session: AsyncSession,
) -> dict[str, int]:
    """Find accounts with tokens expiring soon and refresh them."""
    cutoff = datetime.now(UTC) - timedelta(minutes=TOKEN_AGE_CUTOFF_MINUTES)

    result = await session.execute(
        select(ExternalAccount).where(
            ExternalAccount.needs_reauth.is_(False),
            ExternalAccount.refresh_token.is_not(None),
            ExternalAccount.provider.in_(["google", "o365"]),
            ExternalAccount.last_sync < cutoff,
        )
    )
    accounts = list(result.scalars().all())

    if not accounts:
        logger.info("No accounts need token refresh")
        return {"success": 0, "failed": 0}

    logger.info("Found %d accounts for token refresh", len(accounts))
    success = 0
    failed = 0

    for account in accounts:
        try:
            await _refresh_account_token(session, account)
            success += 1
        except Exception:
            logger.exception("Failed to refresh token for %s", account.external_email)
            account.needs_reauth = True
            failed += 1

    await session.flush()
    logger.info("Token refresh: %d success, %d failed", success, failed)
    return {"success": success, "failed": failed}


async def _refresh_account_token(session: AsyncSession, account: ExternalAccount) -> None:
    """Refresh the OAuth token for a single account."""
    if account.provider not in ("google", "o365"):
        raise ValueError(f"Unsupported provider for token refresh: {account.provider}")

    if account.provider == "google":
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials

        creds = Credentials(
            token=account.token,
            refresh_token=account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=account.client_id,
            client_secret=account.client_secret,
        )
        creds.refresh(Request())
        account.token = creds.token
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
            "client_id": account.client_id,
            "client_secret": account.client_secret,
            "scope": account.scopes or "",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    account.token = data["access_token"]
    if "refresh_token" in data:
        account.refresh_token = data["refresh_token"]
    account.last_sync = datetime.now(UTC)
    logger.info("Refreshed O365 token for %s", account.external_email)


async def token_refresh_loop(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Background loop that refreshes tokens every 30 minutes."""
    logger.info("Starting token refresh background loop")
    while True:
        try:
            async with session_factory() as session:
                await refresh_soon_expiring_tokens(session)
                await session.commit()
        except Exception:
            logger.exception("Error in token refresh loop")
        await asyncio.sleep(REFRESH_INTERVAL_SECONDS)
