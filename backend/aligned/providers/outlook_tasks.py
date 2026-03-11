"""Outlook implementation of the task provider interface."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from msgraph.graph_service_client import GraphServiceClient
from sqlalchemy.ext.asyncio import AsyncSession

from aligned.models.external_account import ExternalAccount
from aligned.providers.o365_credentials import AccessTokenCredential
from aligned.providers.task_provider import ProviderTask, TaskProvider

logger = logging.getLogger(__name__)

INSTRUCTION_TASK_TITLE = "AI Instructions"


class OutlookTaskProvider(TaskProvider):
    """Outlook task provider using Microsoft Graph API."""

    def _get_provider_name(self) -> str:
        return "outlook"

    async def _get_client(
        self, session: AsyncSession, user_id: UUID, task_user_email: str
    ) -> GraphServiceClient | None:
        """Initialize and return a Microsoft Graph client."""
        account = await ExternalAccount.get_by_email_provider_and_user(
            session,
            external_email=task_user_email,
            provider="o365",
            user_id=user_id,
        )
        if not account or not account.token or account.needs_reauth:
            logger.warning("No valid Outlook account for user_id=%s", user_id)
            return None

        credential = AccessTokenCredential(account.token)
        return GraphServiceClient(credential)

    async def authenticate(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> tuple[str, str] | None:
        """Check O365 credentials."""
        account = await ExternalAccount.get_by_email_provider_and_user(
            session,
            external_email=task_user_email,
            provider="o365",
            user_id=user_id,
        )
        if not account:
            return self.provider_name, "/settings"
        if account.needs_reauth:
            return self.provider_name, "/settings"

        client = await self._get_client(session, user_id, task_user_email)
        if not client:
            account.needs_reauth = True
            await session.flush()
            return self.provider_name, "/settings"
        return None

    async def get_tasks(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> list[ProviderTask]:
        """Get all tasks from Outlook via Microsoft Graph API."""
        client = await self._get_client(session, user_id, task_user_email)
        if not client:
            msg = f"Graph client not initialized for user_id={user_id}"
            raise RuntimeError(msg)

        lists_resp = await client.me.todo.lists.get()
        task_lists = (lists_resp.value if lists_resp else None) or []
        all_tasks: list[dict[str, object]] = []

        for task_list in task_lists:
            list_id = task_list.id or ""
            list_name = task_list.display_name or "Tasks"
            tasks_resp = await client.me.todo.lists.by_todo_task_list_id(list_id).tasks.get()
            items = (tasks_resp.value if tasks_resp else None) or []
            for item in items:
                task_dict: dict[str, object] = {
                    "id": item.id,
                    "subject": item.title,
                    "importance": str(item.importance) if item.importance else "normal",
                    "status": "completed" if item.status and str(item.status) == "completed" else "active",
                    "dueDateTime": {"dateTime": item.due_date_time.date_time} if item.due_date_time else None,
                    "listId": list_id,
                    "listName": list_name,
                }
                all_tasks.append(task_dict)

        tasks: list[ProviderTask] = []
        for t in all_tasks:
            if t.get("subject") == INSTRUCTION_TASK_TITLE:
                continue

            due_date = None
            due_dt = t.get("dueDateTime")
            if not due_dt or not isinstance(due_dt, dict) or not due_dt.get("dateTime"):
                pass
            else:
                due_str = due_dt["dateTime"]
                try:
                    due_date = datetime.fromisoformat(str(due_str).replace("Z", "+00:00"))
                except ValueError:
                    logger.exception("Could not parse Outlook due date: %s", due_str)

            priority_map = {"low": 1, "normal": 2, "high": 3, "urgent": 4}
            priority = priority_map.get(str(t.get("importance", "normal")), 2)

            tasks.append(
                ProviderTask(
                    id=str(t["id"]),
                    title=str(t.get("subject", "")),
                    project_id=str(t.get("listId", "")),
                    priority=priority,
                    due_date=due_date,
                    status="completed" if t.get("status") == "completed" else "active",
                    parent_id=None,
                    section_id=None,
                    project_name=str(t.get("listName", "")),
                    provider_task_id=str(t["id"]),
                ),
            )

        return tasks

    async def get_ai_instructions(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> str | None:
        """Get AI instruction task content (stub — partial implementation)."""
        logger.warning("OutlookTaskProvider.get_ai_instructions is a stub")
        return None

    async def update_task(
        self,
        session: AsyncSession,
        user_id: UUID,
        task_id: str,
        task_data: dict[str, object] | None = None,
    ) -> bool:
        """Update task properties (stub — partial implementation)."""
        logger.warning("OutlookTaskProvider.update_task is a stub")
        return True

    async def update_task_status(self, session: AsyncSession, user_id: UUID, task_id: str, status: str) -> bool:
        """Update task status (stub — partial implementation)."""
        logger.warning("OutlookTaskProvider.update_task_status is a stub")
        return True
