"""ExternalAccount model for managing external service accounts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from underway.models.base import Base
from underway.models.types import MySQLUUID

if TYPE_CHECKING:
    from underway.models.user import User

TASK_PROVIDER_MAP: dict[str, str] = {
    "todoist": "todoist",
    "google_tasks": "google",
    "outlook": "o365",
}
PROVIDER_TO_TASK: dict[str, str] = {
    "todoist": "todoist",
    "google": "google_tasks",
    "o365": "outlook",
}


class ExternalAccount(Base):
    """Model for managing all external service accounts (Google, O365, Todoist)."""

    __tablename__ = "external_account"

    id: Mapped[uuid.UUID] = mapped_column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    external_email: Mapped[str] = mapped_column(String(255))
    user_id: Mapped[uuid.UUID] = mapped_column(MySQLUUID, ForeignKey("app_user.id"))
    provider: Mapped[str] = mapped_column(String(50))

    token: Mapped[str | None] = mapped_column(Text, default=None)
    api_key: Mapped[str | None] = mapped_column(String(255), default=None)
    refresh_token: Mapped[str | None] = mapped_column(Text, default=None)
    token_uri: Mapped[str | None] = mapped_column(String(255), default=None)
    client_id: Mapped[str | None] = mapped_column(String(255), default=None)
    client_secret: Mapped[str | None] = mapped_column(String(255), default=None)
    scopes: Mapped[str | None] = mapped_column(Text, default=None)

    write_calendar: Mapped[bool] = mapped_column(default=False)
    write_tasks: Mapped[bool] = mapped_column(default=False)
    use_for_calendar: Mapped[bool] = mapped_column(default=False)
    use_for_tasks: Mapped[bool] = mapped_column(default=False)
    needs_reauth: Mapped[bool] = mapped_column(default=False)

    last_sync: Mapped[datetime | None] = mapped_column(default=None)
    expires_at: Mapped[datetime | None] = mapped_column(default=None)
    created_at: Mapped[datetime | None] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: Mapped[User] = relationship(back_populates="external_accounts")

    def __repr__(self) -> str:
        return f"<ExternalAccount {self.external_email} ({self.provider})>"

    @classmethod
    async def get_accounts_for_user(cls, session: AsyncSession, user_id: uuid.UUID) -> list[ExternalAccount]:

        result = await session.execute(select(cls).where(cls.user_id == user_id))
        return list(result.scalars().all())

    @classmethod
    async def get_writable_account(
        cls, session: AsyncSession, user_id: uuid.UUID, account_type: str
    ) -> ExternalAccount | None:
        if account_type not in ("calendar", "tasks"):
            raise ValueError("account_type must be 'calendar' or 'tasks'")

        if account_type == "calendar":
            stmt = select(cls).where(cls.user_id == user_id, cls.write_calendar.is_(True))
        else:
            stmt = select(cls).where(cls.user_id == user_id, cls.write_tasks.is_(True))

        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def get_task_accounts_for_user(cls, session: AsyncSession, user_id: uuid.UUID) -> list[ExternalAccount]:

        stmt = (
            select(cls)
            .where(
                cls.user_id == user_id,
                cls.use_for_tasks.is_(True),
                cls.needs_reauth.is_(False),
                cls.token.is_not(None),
            )
            .order_by(cls.provider, cls.external_email)
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_task_account(
        cls,
        session: AsyncSession,
        user_id: uuid.UUID,
        provider_name: str,
        task_user_email: str,
    ) -> ExternalAccount | None:
        """Get a specific task account by provider name and email."""

        # Map task provider name to DB provider name
        db_provider = TASK_PROVIDER_MAP.get(provider_name, provider_name)
        result = await session.execute(
            select(cls).where(
                cls.user_id == user_id,
                cls.provider == db_provider,
                cls.external_email == task_user_email,
                cls.use_for_tasks.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def disconnect(self, purpose: str, session: AsyncSession) -> None:
        """Disconnect this account from a purpose (calendar or tasks).

        Soft delete: if still used for the other purpose, clear the flag.
        Hard delete: if no longer used for either purpose, delete the row.
        Auto-reassign primary if this was the primary account.
        """
        if purpose not in ("calendar", "tasks"):
            raise ValueError("purpose must be 'calendar' or 'tasks'")

        was_writable = False
        if purpose == "calendar":
            was_writable = self.write_calendar
            self.use_for_calendar = False
            self.write_calendar = False
        else:
            was_writable = self.write_tasks
            self.use_for_tasks = False
            self.write_tasks = False

        if not self.use_for_calendar and not self.use_for_tasks:
            await session.delete(self)
            await session.flush()
        else:
            await session.flush()

        if was_writable:
            write_col = "write_calendar" if purpose == "calendar" else "write_tasks"
            use_col = "use_for_calendar" if purpose == "calendar" else "use_for_tasks"
            stmt = select(ExternalAccount).where(
                ExternalAccount.user_id == self.user_id,
                ExternalAccount.provider == self.provider,
                getattr(ExternalAccount, use_col).is_(True),
                ExternalAccount.id != self.id,
            )
            result = await session.execute(stmt)
            candidate = result.scalars().first()
            if candidate:
                setattr(candidate, write_col, True)
                await session.flush()

    @classmethod
    async def get_by_email_provider_and_user(
        cls,
        session: AsyncSession,
        external_email: str,
        provider: str,
        user_id: uuid.UUID,
    ) -> ExternalAccount | None:
        """Get an account by email, provider, and user."""

        result = await session.execute(
            select(cls).where(
                cls.user_id == user_id,
                cls.provider == provider,
                cls.external_email == external_email,
            )
        )
        return result.scalar_one_or_none()
