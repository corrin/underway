"""OAuthState model — short-lived DB-backed store for OAuth PKCE flows."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from underway.models.base import Base
from underway.models.types import MySQLUUID

STATE_TTL_MINUTES = 10


class OAuthState(Base):
    """Short-lived record tying an OAuth state parameter to a user + PKCE verifier.

    Created when we redirect the user to the provider's consent screen.
    Consumed (and deleted) exactly once when the callback arrives.
    Rows older than STATE_TTL_MINUTES are considered expired.
    """

    __tablename__ = "oauth_state"

    state: Mapped[str] = mapped_column(String(255), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(MySQLUUID, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)  # "google" | "o365"
    # PKCE code_verifier for Google flows; NULL for O365 (uses plain state)
    code_verifier: Mapped[str | None] = mapped_column(Text, default=None)
    expires_at: Mapped[datetime] = mapped_column(nullable=False)

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        *,
        state: str,
        user_id: uuid.UUID,
        provider: str,
        code_verifier: str | None = None,
    ) -> "OAuthState":
        record = cls(
            state=state,
            user_id=user_id,
            provider=provider,
            code_verifier=code_verifier,
            expires_at=datetime.now(UTC) + timedelta(minutes=STATE_TTL_MINUTES),
        )
        session.add(record)
        await session.flush()
        return record

    @classmethod
    async def consume(
        cls,
        session: AsyncSession,
        state: str,
    ) -> "OAuthState | None":
        """Fetch and delete the state record in one operation. Returns None if missing or expired."""
        result = await session.execute(select(cls).where(cls.state == state))
        record = result.scalar_one_or_none()
        if record is None:
            return None
        if record.expires_at.replace(tzinfo=UTC) < datetime.now(UTC):
            await session.delete(record)
            await session.flush()
            return None
        await session.delete(record)
        await session.flush()
        return record
