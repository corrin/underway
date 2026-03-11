"""Todoist implementation of the task provider interface."""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from todoist_api_python.api import TodoistAPI

from aligned.models.external_account import ExternalAccount
from aligned.models.task import Task
from aligned.providers.task_provider import ProviderTask, TaskProvider

logger = logging.getLogger(__name__)

INSTRUCTION_TASK_TITLE = "AI Instructions"


class TodoistProvider(TaskProvider):
    """Todoist task provider using the Todoist API."""

    def _get_provider_name(self) -> str:
        return "todoist"

    async def _get_api(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> TodoistAPI | None:
        """Get a Todoist API client using credentials from the database."""
        account = await ExternalAccount.get_task_account(
            session,
            user_id=user_id,
            provider_name=self.provider_name,
            task_user_email=task_user_email,
        )
        if account and account.api_key:
            return TodoistAPI(account.api_key)
        logger.warning("No Todoist account for user_id=%s, email=%s", user_id, task_user_email)
        return None

    async def authenticate(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> tuple[str, str] | None:
        """Check credentials; return (provider_name, auth_url) if auth needed."""
        account = await ExternalAccount.get_task_account(
            session,
            user_id=user_id,
            provider_name=self.provider_name,
            task_user_email=task_user_email,
        )
        if not account or not account.api_key:
            return self.provider_name, "/settings"  # redirect to settings to add key

        # Test the key
        try:
            api = TodoistAPI(account.api_key)
            # Consume one page to verify credentials
            next(iter(api.get_projects()), None)
            return None  # authenticated
        except Exception:
            logger.exception("Todoist credentials invalid for user_id=%s", user_id)
            return self.provider_name, "/settings"

    async def get_tasks(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> list[ProviderTask]:
        """Get all tasks from Todoist."""
        api = await self._get_api(session, user_id, task_user_email)
        if not api:
            msg = f"Todoist API not initialized for user_id={user_id}"
            raise RuntimeError(msg)

        # Get projects for name mapping
        projects: dict[str, str] = {}
        for page in api.get_projects():
            for p in page:
                projects[p.id] = p.name

        tasks: list[ProviderTask] = []

        for task_page in api.get_tasks():
            for t in task_page:
                if t.content == INSTRUCTION_TASK_TITLE:
                    continue

                due_date = None
                if t.due:
                    due_date_str = str(t.due.date)
                    due_date = datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))

                tasks.append(
                    ProviderTask(
                        id=t.id,
                        title=t.content,
                        project_id=t.project_id,
                        priority=t.priority,
                        due_date=due_date,
                        status="completed" if t.is_completed else "active",
                        parent_id=getattr(t, "parent_id", None),
                        section_id=getattr(t, "section_id", None),
                        project_name=projects.get(t.project_id),
                        provider_task_id=t.id,
                    ),
                )

        logger.info("[TODOIST] Retrieved %d tasks for user_id=%s", len(tasks), user_id)
        return tasks

    async def get_ai_instructions(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> str | None:
        """Get the AI instruction task content."""
        api = await self._get_api(session, user_id, task_user_email)
        if not api:
            msg = f"Todoist API not initialized for user_id={user_id}"
            raise RuntimeError(msg)

        for page in api.filter_tasks(query=f"search:{INSTRUCTION_TASK_TITLE}"):
            for t in page:
                if t.content == INSTRUCTION_TASK_TITLE:
                    return str(t.description) if t.description else None
        return None

    async def update_task(
        self,
        session: AsyncSession,
        user_id: UUID,
        task_id: str,
        task_data: dict[str, object] | None = None,
    ) -> bool:
        """Update task properties in Todoist."""
        if not task_data:
            return True

        result = await session.execute(select(Task).where(Task.id == task_id, Task.user_id == user_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        api = await self._get_api(session, user_id, task.task_user_email or "")
        if not api:
            msg = f"Todoist API not initialized for user_id={user_id}"
            raise RuntimeError(msg)

        provider_task_id = task.provider_task_id

        # Handle status changes
        if "status" in task_data:
            if task_data["status"] == "completed":
                api.complete_task(provider_task_id)
            else:
                api.uncomplete_task(provider_task_id)

        # Handle other field updates
        if "title" in task_data:
            api.update_task(task_id=provider_task_id, content=str(task_data["title"]))
        if "due_date" in task_data:
            if task_data["due_date"]:
                api.update_task(task_id=provider_task_id, due_string=str(task_data["due_date"]))
            else:
                api.update_task(task_id=provider_task_id, due_string="")
        if "priority" in task_data:
            api.update_task(task_id=provider_task_id, priority=5 - int(str(task_data["priority"])))

        return True

    async def update_task_status(self, session: AsyncSession, user_id: UUID, task_id: str, status: str) -> bool:
        """Update task completion status in Todoist."""
        result = await session.execute(select(Task).where(Task.id == task_id, Task.user_id == user_id))
        task = result.scalar_one_or_none()
        if not task:
            raise ValueError(f"Task {task_id} not found")

        api = await self._get_api(session, user_id, task.task_user_email or "")
        if not api:
            msg = f"Todoist API not initialized for user_id={user_id}"
            raise RuntimeError(msg)

        provider_task_id = task.provider_task_id

        if status == "completed":
            api.complete_task(provider_task_id)
        else:
            api.uncomplete_task(provider_task_id)

        logger.info("[TODOIST] Updated task %s status to %s", task_id, status)
        return True
