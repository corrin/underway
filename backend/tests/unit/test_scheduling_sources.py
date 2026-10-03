"""Source identities, pagination, and source-first completion."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from underway.models.task import Task
from underway.models.user import User
from underway.providers.google_tasks import GoogleTaskProvider
from underway.providers.task_manager import TaskManager
from underway.providers.task_provider import ProviderTask
from underway.scheduling.schemas import SourceRef
from underway.services.task_actions import edit_task
from underway.services.task_sync import sync_provider_tasks


async def test_google_reads_every_list_and_task_page_with_stable_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    provider = GoogleTaskProvider()
    client = MagicMock()
    client.tasklists.return_value.list.return_value.execute.side_effect = [
        {"items": [{"id": "list1", "title": "One"}], "nextPageToken": "lists-next"},
        {"items": [{"id": "list2", "title": "Two"}]},
    ]
    client.tasks.return_value.list.return_value.execute.side_effect = [
        {"items": [{"id": "t1", "title": "First", "notes": "Resume here"}], "nextPageToken": "tasks-next"},
        {"items": [{"id": "t2", "title": "Second", "parent": "t1"}]},
        {"items": [{"id": "t3", "title": "Third"}]},
    ]
    monkeypatch.setattr(provider, "_get_client", AsyncMock(return_value=client))
    tasks = await provider.get_tasks(AsyncMock(spec=AsyncSession), uuid4(), "me")
    assert [task.id for task in tasks] == ["t1", "t2", "t3"]
    assert tasks[0].description == "Resume here"
    assert tasks[1].parent_id == "t1"
    assert tasks[2].project_id == "list2"
    assert client.tasks.return_value.list.call_args_list[1].kwargs["pageToken"] == "tasks-next"


def test_task_identity_survives_project_move_and_scopes_account() -> None:
    original = SourceRef(provider="todoist", account="me", container_id="old", task_id="t")
    assert original.key == original.model_copy(update={"container_id": "new"}).key
    assert original.key != original.model_copy(update={"account": "other"}).key


async def test_sync_keeps_same_external_id_in_two_accounts_separate(db_session: AsyncSession) -> None:
    user = User(id=uuid4(), app_login="sources@example.com")
    db_session.add(user)
    await db_session.flush()
    task = ProviderTask(
        id="legacy-random-id",
        provider_task_id="stable",
        title="One",
        project_id="p",
        priority=2,
        status="active",
        due_date=None,
    )
    for account in ("one", "two"):
        await sync_provider_tasks(db_session, user.id, account, "google_tasks", [task])
        await db_session.flush()
    rows = list((await db_session.scalars(select(Task))).all())
    assert len(rows) == 2
    assert {row.provider_task_id for row in rows} == {"stable"}
    task.title = "Changed"
    await sync_provider_tasks(db_session, user.id, "one", "google_tasks", [task])
    assert next(row for row in rows if row.task_user_email == "two").title == "One"


async def test_failed_source_completion_never_marks_cache_complete(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = User(id=uuid4(), app_login="completion@example.com")
    db_session.add(user)
    await db_session.flush()
    source = ProviderTask(id="stable", title="Recurring", project_id="p", priority=2, status="active", due_date=None)
    await sync_provider_tasks(db_session, user.id, "me", "todoist", [source])
    task = await db_session.scalar(select(Task))
    assert task is not None
    provider = AsyncMock()
    provider.update_task.side_effect = RuntimeError("offline")
    monkeypatch.setattr(TaskManager, "get_provider", lambda self, name: provider)
    with pytest.raises(RuntimeError, match="offline"):
        await edit_task(db_session, task, {"status": "completed"})
    assert task.status == "active"
    provider.get_tasks.assert_not_awaited()
    provider.update_task.side_effect = None
    provider.update_task.return_value = True
    task.list_type = "completed"  # Simulate moving the card into the completed list.
    source.due_date = datetime(2026, 10, 12)
    provider.get_tasks.return_value = [source]
    result = await edit_task(db_session, task, {"status": "completed"})
    assert result["source_updated"]
    assert task.status == "active"
    assert task.due_date == datetime(2026, 10, 12)
    assert task.list_type == "unprioritized"
