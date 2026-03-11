"""Google Tasks implementation of the task provider interface."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from uuid import UUID

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient._apis.tasks.v1 import TasksResource
from googleapiclient.discovery import build
from sqlalchemy.ext.asyncio import AsyncSession

from aligned.models.external_account import ExternalAccount
from aligned.providers.task_provider import ProviderTask, TaskProvider

logger = logging.getLogger(__name__)

INSTRUCTION_TASK_TITLE = "AI Instructions"


class GoogleTaskProvider(TaskProvider):
    """Google Tasks provider using the Google Tasks API."""

    def _get_provider_name(self) -> str:
        return "google_tasks"

    async def _get_client(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> TasksResource | None:
        """Initialize and return a Google Tasks API client."""
        account = await ExternalAccount.get_by_email_provider_and_user(
            session,
            external_email=task_user_email,
            provider="google",
            user_id=user_id,
        )
        if not account or account.needs_reauth:
            logger.warning("No valid Google account for user_id=%s", user_id)
            return None

        creds = Credentials(
            token=account.token,
            refresh_token=account.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=account.client_id,
            client_secret=account.client_secret,
        )

        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            account.token = creds.token
            await session.flush()

        return build("tasks", "v1", credentials=creds)

    async def authenticate(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> tuple[str, str] | None:
        """Check Google credentials."""
        account = await ExternalAccount.get_by_email_provider_and_user(
            session,
            external_email=task_user_email,
            provider="google",
            user_id=user_id,
        )
        if not account or account.needs_reauth:
            return self.provider_name, "/settings"

        client = await self._get_client(session, user_id, task_user_email)
        if not client:
            return self.provider_name, "/settings"

        return None

    async def get_tasks(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> list[ProviderTask]:
        """Get all tasks from Google Tasks API."""
        client = await self._get_client(session, user_id, task_user_email)
        if not client:
            msg = f"Google Tasks client not initialized for user_id={user_id}"
            raise RuntimeError(msg)

        result = client.tasklists().list().execute()
        task_lists = result.get("items", [])
        all_tasks: list[dict[str, object]] = []

        for task_list in task_lists:
            list_id = task_list["id"]
            list_name = task_list.get("title", "Tasks")
            task_result = client.tasks().list(tasklist=list_id, showCompleted=False, showHidden=True).execute()
            items = task_result.get("items", [])
            for item in items:
                task_dict: dict[str, object] = dict(item)
                task_dict["listId"] = list_id
                task_dict["listName"] = list_name
                all_tasks.append(task_dict)

        tasks: list[ProviderTask] = []
        for t in all_tasks:
            if t.get("title") == INSTRUCTION_TASK_TITLE:
                continue

            due_date = None
            due_str = t.get("due")
            if due_str:
                for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
                    try:
                        due_date = datetime.strptime(str(due_str), fmt)
                        break
                    except ValueError:
                        continue

            tasks.append(
                ProviderTask(
                    id=str(uuid.uuid4()),
                    title=str(t.get("title", "")),
                    project_id=str(t.get("listId", "")),
                    priority=2,  # Google Tasks has no priority
                    due_date=due_date,
                    status="completed" if t.get("status") == "completed" else "active",
                    parent_id=str(t["parent"]) if t.get("parent") else None,
                    section_id=None,
                    project_name=str(t.get("listName", "")),
                    provider_task_id=str(t["id"]),
                ),
            )

        return tasks

    async def get_ai_instructions(self, session: AsyncSession, user_id: UUID, task_user_email: str) -> str | None:
        """Get AI instruction task content (stub — partial implementation)."""
        logger.warning("GoogleTaskProvider.get_ai_instructions is a stub")
        return None

    async def update_task(
        self,
        session: AsyncSession,
        user_id: UUID,
        task_id: str,
        task_data: dict[str, object] | None = None,
    ) -> bool:
        """Update task properties (stub — partial implementation)."""
        logger.warning("GoogleTaskProvider.update_task is a stub")
        return True

    async def update_task_status(self, session: AsyncSession, user_id: UUID, task_id: str, status: str) -> bool:
        """Update task status (stub — partial implementation)."""
        logger.warning("GoogleTaskProvider.update_task_status is a stub")
        return True
