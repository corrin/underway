"""Unit tests for task sync service."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from underway.models.task import Task
from underway.models.user import User
from underway.providers.task_provider import ProviderTask
from underway.services.task_sync import _compute_hash, sync_provider_tasks, sync_task_deletions


async def _create_user(session: AsyncSession, email: str = "sync@example.com") -> User:
    user = User(app_login=email)
    user.id = uuid.uuid4()
    session.add(user)
    await session.flush()
    return user


def _make_provider_task(**kwargs: object) -> ProviderTask:
    defaults = {
        "id": str(uuid.uuid4()),
        "title": "Test task",
        "project_id": "proj1",
        "priority": 2,
        "due_date": None,
        "status": "active",
        "provider_task_id": None,
    }
    defaults.update(kwargs)
    defaults.setdefault("provider_task_id", defaults["id"])
    return ProviderTask(**defaults)  # type: ignore[arg-type]


class TestComputeHash:
    def test_same_content_same_hash(self) -> None:
        t1 = _make_provider_task(id="1", title="A")
        t2 = _make_provider_task(id="1", title="A")
        assert _compute_hash(t1) == _compute_hash(t2)

    def test_different_content_different_hash(self) -> None:
        t1 = _make_provider_task(id="1", title="A")
        t2 = _make_provider_task(id="1", title="B")
        assert _compute_hash(t1) != _compute_hash(t2)


class TestSyncProviderTasks:
    async def test_creates_new_tasks(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        pt = _make_provider_task(title="From provider")

        count = await sync_provider_tasks(db_session, user.id, "test@example.com", "todoist", [pt])
        assert count == 1

        result = await db_session.execute(select(Task).where(Task.user_id == user.id))
        task = result.scalar_one()
        assert task.title == "From provider"
        assert task.provider == "todoist"
        assert task.list_type == "unprioritized"

    async def test_updates_changed_tasks(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        pt = _make_provider_task(title="Original")

        await sync_provider_tasks(db_session, user.id, "test@example.com", "todoist", [pt])

        pt_updated = _make_provider_task(id=pt.id, title="Updated")
        count = await sync_provider_tasks(db_session, user.id, "test@example.com", "todoist", [pt_updated])
        assert count == 1

        result = await db_session.execute(select(Task).where(Task.user_id == user.id))
        task = result.scalar_one()
        assert task.title == "Updated"

    async def test_skips_unchanged_tasks(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        pt = _make_provider_task(title="Same")

        await sync_provider_tasks(db_session, user.id, "test@example.com", "todoist", [pt])
        count = await sync_provider_tasks(db_session, user.id, "test@example.com", "todoist", [pt])
        assert count == 0


class TestSyncTaskDeletions:
    async def test_deletes_tasks_not_in_provider(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)

        # Create two tasks in DB
        t1 = Task(
            user_id=user.id,
            provider="todoist",
            provider_task_id="keep",
            title="Keep",
            status="active",
            content_hash="a",
            list_type="unprioritized",
            position=0,
        )
        t2 = Task(
            user_id=user.id,
            provider="todoist",
            provider_task_id="remove",
            title="Remove",
            status="active",
            content_hash="b",
            list_type="unprioritized",
            position=1,
        )
        db_session.add_all([t1, t2])
        await db_session.flush()

        deleted = await sync_task_deletions(db_session, user.id, "todoist", ["keep"])
        assert deleted == 1

        result = await db_session.execute(select(Task).where(Task.user_id == user.id))
        remaining = list(result.scalars().all())
        assert len(remaining) == 1
        assert remaining[0].provider_task_id == "keep"
