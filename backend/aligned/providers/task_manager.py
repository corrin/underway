"""Task manager — coordinator that instantiates and manages all task providers."""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from aligned.providers.google_tasks import GoogleTaskProvider
from aligned.providers.outlook_tasks import OutlookTaskProvider
from aligned.providers.task_provider import ProviderTask, TaskProvider
from aligned.providers.todoist import TodoistProvider

logger = logging.getLogger(__name__)


class TaskManager:
    """Manages task providers (Todoist, Outlook, Google Tasks)."""

    def __init__(self) -> None:
        self.providers: dict[str, TaskProvider] = {}
        self._provider_classes: dict[str, type[TaskProvider]] = {
            "todoist": TodoistProvider,
            "outlook": OutlookTaskProvider,
            "google_tasks": GoogleTaskProvider,
        }
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        for name, cls in self._provider_classes.items():
            self.providers[name] = cls()
            logger.debug("Initialized %s provider", name)

    def get_provider(self, provider_name: str) -> TaskProvider:
        provider = self.providers.get(provider_name)
        if provider is None:
            raise ValueError(f"Task provider '{provider_name}' not found.")
        return provider

    def get_available_providers(self) -> list[str]:
        return list(self.providers.keys())

    async def authenticate(
        self,
        session: AsyncSession,
        user_id: UUID,
        task_user_email: str,
        provider_name: str | None = None,
    ) -> dict[str, tuple[str, str] | None]:
        """Authenticate with specified or all providers."""
        providers_to_check = {provider_name: self.providers[provider_name]} if provider_name else self.providers
        results: dict[str, tuple[str, str] | None] = {}

        for name, provider in providers_to_check.items():
            result = await provider.authenticate(session, user_id, task_user_email)
            results[name] = result

        return results

    async def get_tasks(
        self,
        session: AsyncSession,
        user_id: UUID,
        task_user_email: str,
        provider_name: str,
    ) -> list[ProviderTask]:
        """Get tasks from a specific provider."""
        provider = self.get_provider(provider_name)
        return await provider.get_tasks(session, user_id, task_user_email)

    async def get_ai_instructions(
        self,
        session: AsyncSession,
        user_id: UUID,
        task_user_email: str,
        provider_name: str | None = None,
    ) -> str | None:
        """Get AI instructions from specified or first available provider."""
        provider = self.get_provider(provider_name) if provider_name else next(iter(self.providers.values()))
        return await provider.get_ai_instructions(session, user_id, task_user_email)

    async def update_task_status(
        self,
        session: AsyncSession,
        user_id: UUID,
        task_id: str,
        status: str,
        provider_name: str,
    ) -> bool:
        """Update task status via the appropriate provider."""
        provider = self.get_provider(provider_name)
        return await provider.update_task_status(session, user_id, task_id, status)
