"""Base class for task providers (Todoist, Google Tasks, Outlook)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


@dataclass
class ProviderTask:
    """Represents a task fetched from an external provider."""

    id: str
    title: str
    project_id: str
    priority: int
    due_date: datetime | None
    status: str
    parent_id: str | None = None
    section_id: str | None = None
    project_name: str | None = None
    provider_task_id: str | None = None


class TaskProvider(ABC):
    """Base class for task providers."""

    def __init__(self) -> None:
        self.provider_name = self._get_provider_name()

    @abstractmethod
    def _get_provider_name(self) -> str:
        """Return the name of this provider (e.g., 'todoist')."""

    @abstractmethod
    async def authenticate(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> tuple[str, str] | None:
        """Check credentials and return (provider_name, auth_url) if auth needed, else None."""

    @abstractmethod
    async def get_tasks(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> list[ProviderTask]:
        """Get all tasks for the user from this provider."""

    @abstractmethod
    async def get_ai_instructions(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> str | None:
        """Get the AI instruction task content."""

    @abstractmethod
    async def update_task(
        self,
        session: AsyncSession,
        user_id: UUID,
        task_id: str,
        task_data: dict[str, object] | None = None,
    ) -> bool:
        """Update multiple task properties."""

    @abstractmethod
    async def update_task_status(self, session: AsyncSession, user_id: UUID, task_id: str, status: str) -> bool:
        """Update task completion status."""
