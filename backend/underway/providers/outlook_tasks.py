"""Outlook implementation of the task provider interface."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from msgraph.generated.models.body_type import BodyType
from msgraph.generated.models.importance import Importance
from msgraph.generated.models.item_body import ItemBody
from msgraph.generated.models.task_status import TaskStatus
from msgraph.generated.models.todo_task import TodoTask
from msgraph.graph_service_client import GraphServiceClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from underway.models.external_account import ExternalAccount
from underway.models.task import Task
from underway.providers.o365_credentials import AccessTokenCredential
from underway.providers.task_provider import ProviderTask, TaskProvider

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
        if lists_resp is None:
            raise RuntimeError("Incomplete Microsoft To Do list response.")
        else:
            task_lists = lists_resp.value or []
        while lists_resp and lists_resp.odata_next_link:
            lists_resp = await client.me.todo.lists.with_url(lists_resp.odata_next_link).get()
            if lists_resp is None:
                raise RuntimeError("Incomplete Microsoft To Do list response.")
            else:
                task_lists.extend(lists_resp.value or [])
        all_tasks: list[dict[str, object]] = []

        for task_list in task_lists:
            list_id = task_list.id or ""
            list_name = task_list.display_name or "Tasks"
            tasks_resp = await client.me.todo.lists.by_todo_task_list_id(list_id).tasks.get()
            if tasks_resp is None:
                raise RuntimeError("Incomplete Microsoft To Do task response.")
            else:
                items = tasks_resp.value or []
            while tasks_resp and tasks_resp.odata_next_link:
                tasks_resp = (
                    await client.me.todo.lists.by_todo_task_list_id(list_id)
                    .tasks.with_url(tasks_resp.odata_next_link)
                    .get()
                )
                if tasks_resp is None:
                    raise RuntimeError("Incomplete Microsoft To Do task response.")
                else:
                    items.extend(tasks_resp.value or [])
            for item in items:
                task_dict: dict[str, object] = {
                    "id": item.id,
                    "subject": item.title,
                    "importance": item.importance.value if item.importance else "normal",
                    "status": "completed" if item.status == TaskStatus.Completed else "active",
                    "description": item.body.content if item.body else "",
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
                    description=str(t.get("description") or ""),
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
        """Apply edits through Microsoft Graph before acknowledging completion."""
        task = await session.scalar(select(Task).where(Task.id == task_id, Task.user_id == user_id))
        if task is None or not task.project_id:
            raise ValueError("Task not found or missing its source list.")
        else:
            client = await self._get_client(session, user_id, task.task_user_email or "")
        if client is None:
            raise ValueError("Microsoft To Do requires authentication.")
        else:
            data = task_data or {}
        body = TodoTask()
        if "priority" in data:
            priority = int(str(data["priority"]))
            body.importance = (
                Importance.High if priority >= 3 else Importance.Low if priority == 1 else Importance.Normal
            )
        else:
            pass
        if "status" in data:
            body.status = TaskStatus.Completed if data["status"] == "completed" else TaskStatus.NotStarted
        else:
            pass
        if "title" in data:
            body.title = str(data["title"])
        else:
            pass
        if "description" in data:
            body.body = ItemBody(content=str(data["description"] or ""), content_type=BodyType.Text)
        else:
            pass
        await (
            client.me.todo.lists.by_todo_task_list_id(task.project_id)
            .tasks.by_todo_task_id(task.provider_task_id)
            .patch(body)
        )
        return True

    async def update_task_status(self, session: AsyncSession, user_id: UUID, task_id: str, status: str) -> bool:
        return await self.update_task(session, user_id, task_id, {"status": status})
