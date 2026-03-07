"""Task model — schema and read-only queries only. Business logic deferred to Phase 2."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from aligned.models.base import Base
from aligned.models.types import MySQLUUID

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class Task(Base):
    """Tracks tasks across all providers."""

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(MySQLUUID, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(MySQLUUID, ForeignKey("app_user.id"), index=True)

    task_user_email: Mapped[str | None] = mapped_column(String(255), index=True, default=None)
    provider: Mapped[str] = mapped_column(String(50))
    provider_task_id: Mapped[str] = mapped_column(String(255))

    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(String(50))
    due_date: Mapped[datetime | None] = mapped_column(default=None)
    priority: Mapped[int | None] = mapped_column(default=None)

    project_id: Mapped[str | None] = mapped_column(String(255), default=None)
    project_name: Mapped[str | None] = mapped_column(String(255), default=None)
    parent_id: Mapped[str | None] = mapped_column(String(255), default=None)
    section_id: Mapped[str | None] = mapped_column(String(255), default=None)

    list_type: Mapped[str | None] = mapped_column(String(50), default="unprioritized")
    position: Mapped[int | None] = mapped_column(Integer, default=0)

    content_hash: Mapped[str] = mapped_column(String(64))
    last_synced: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))
    created_at: Mapped[datetime | None] = mapped_column(default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime | None] = mapped_column(
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "task_user_email",
            "provider",
            "provider_task_id",
            name="uq_user_id_task_user_provider_task",
        ),
    )

    def to_dict(self) -> dict[str, object]:
        return {
            "id": str(self.id),
            "user_id": str(self.user_id),
            "task_user_email": self.task_user_email,
            "provider": self.provider,
            "provider_task_id": self.provider_task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "priority": self.priority,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "parent_id": self.parent_id,
            "section_id": self.section_id,
            "list_type": self.list_type,
            "position": self.position,
            "last_synced": self.last_synced.isoformat() if self.last_synced else None,
        }

    @classmethod
    async def get_user_tasks_by_list(
        cls, session: AsyncSession, user_id: uuid.UUID
    ) -> tuple[list[Task], list[Task], list[Task]]:
        from sqlalchemy import select

        prioritized_result = await session.execute(
            select(cls)
            .where(cls.user_id == user_id, cls.list_type == "prioritized", cls.status == "active")
            .order_by(cls.position)
        )
        unprioritized_result = await session.execute(
            select(cls)
            .where(cls.user_id == user_id, cls.list_type == "unprioritized", cls.status == "active")
            .order_by(cls.position)
        )
        completed_result = await session.execute(
            select(cls).where(cls.user_id == user_id, cls.status == "completed").order_by(cls.position)
        )
        return (
            list(prioritized_result.scalars().all()),
            list(unprioritized_result.scalars().all()),
            list(completed_result.scalars().all()),
        )

    def __repr__(self) -> str:
        return f"<Task {self.id} '{self.title}'>"
