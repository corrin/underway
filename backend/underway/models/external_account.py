"""ExternalAccount model for managing external service accounts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, and_, or_, select, update
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
    scopes: Mapped[str | None] = mapped_column(Text, default=None)

    is_primary_calendar: Mapped[bool] = mapped_column(default=False)
    is_primary_tasks: Mapped[bool] = mapped_column(default=False)
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
    async def set_as_primary(
        cls,
        session: AsyncSession,
        external_email: str,
        provider: str,
        user_id: uuid.UUID,
        account_type: str,
    ) -> None:
        if account_type not in ("calendar", "tasks"):
            raise ValueError("account_type must be 'calendar' or 'tasks'")

        result = await session.execute(
            select(cls).where(
                cls.external_email == external_email,
                cls.provider == provider,
                cls.user_id == user_id,
            )
        )
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError("Account not found")

        if account_type == "calendar":
            await session.execute(update(cls).where(cls.user_id == user_id).values(is_primary_calendar=False))
            account.is_primary_calendar = True
        else:
            await session.execute(update(cls).where(cls.user_id == user_id).values(is_primary_tasks=False))
            account.is_primary_tasks = True

    @classmethod
    async def get_primary_account(
        cls, session: AsyncSession, user_id: uuid.UUID, account_type: str
    ) -> ExternalAccount | None:
        if account_type not in ("calendar", "tasks"):
            raise ValueError("account_type must be 'calendar' or 'tasks'")

        if account_type == "calendar":
            stmt = select(cls).where(cls.user_id == user_id, cls.is_primary_calendar.is_(True))
        else:
            stmt = select(cls).where(cls.user_id == user_id, cls.is_primary_tasks.is_(True))

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
                or_(
                    and_(cls.provider == "todoist", cls.api_key.is_not(None)),
                    and_(cls.provider.in_(["google", "o365"]), cls.token.is_not(None)),
                ),
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
