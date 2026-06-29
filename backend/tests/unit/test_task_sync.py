"""Unit tests for task sync service."""

import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from underway.models.external_account import ExternalAccount
from underway.models.task import Task
from underway.models.user import User
from underway.providers.task_manager import TaskManager
from underway.providers.task_provider import ProviderTask
from underway.services.task_sync import (
    _compute_hash,
    sync_all_task_accounts,
    sync_provider_tasks,
    sync_task_deletions,
)


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


class _FakeTaskManager(TaskManager):
    """TaskManager whose get_tasks returns canned tasks per account email (no network)."""

    def __init__(
        self,
        tasks_by_email: dict[str, list[ProviderTask]],
        fail_emails: set[str] | None = None,
    ) -> None:
        super().__init__()
        self._tasks_by_email = tasks_by_email
        self._fail_emails = fail_emails or set()
        self.calls: list[tuple[str, str]] = []

    async def get_tasks(
        self,
        session: AsyncSession,
        user_id: UUID,
        task_user_email: str,
        provider_name: str,
    ) -> list[ProviderTask]:
        self.calls.append((task_user_email, provider_name))
        if task_user_email in self._fail_emails:
            raise RuntimeError("provider boom")
        else:
            return self._tasks_by_email.get(task_user_email, [])


async def _create_task_account(
    session: AsyncSession,
    user: User,
    provider: str,
    email: str,
) -> ExternalAccount:
    account = ExternalAccount(
        user_id=user.id,
        external_email=email,
        provider=provider,
        use_for_tasks=True,
        needs_reauth=False,
        api_key="key" if provider == "todoist" else None,
        token=None if provider == "todoist" else "tok",
    )
    session.add(account)
    await session.flush()
    return account


class TestSyncAllTaskAccounts:
    async def test_maps_db_provider_to_task_provider(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await _create_task_account(db_session, user, "todoist", "td@example.com")
        await _create_task_account(db_session, user, "google", "g@example.com")
        await _create_task_account(db_session, user, "o365", "o@example.com")

        manager = _FakeTaskManager(tasks_by_email={})
        summary = await sync_all_task_accounts(db_session, user.id, manager)

        assert summary == {"accounts": 3, "upserted": 0, "failed": 0}
        # Accounts come back ordered by provider name: google, o365, todoist.
        assert manager.calls == [
            ("g@example.com", "google_tasks"),
            ("o@example.com", "outlook"),
            ("td@example.com", "todoist"),
        ]

    async def test_syncs_provider_tasks_into_db(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await _create_task_account(db_session, user, "todoist", "td@example.com")
        pt = _make_provider_task(title="Imported")

        manager = _FakeTaskManager(tasks_by_email={"td@example.com": [pt]})
        summary = await sync_all_task_accounts(db_session, user.id, manager)

        assert summary == {"accounts": 1, "upserted": 1, "failed": 0}
        result = await db_session.execute(select(Task).where(Task.user_id == user.id))
        task = result.scalar_one()
        assert task.title == "Imported"
        assert task.provider == "todoist"

    async def test_one_failing_account_does_not_abort_others(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        await _create_task_account(db_session, user, "todoist", "ok@example.com")
        await _create_task_account(db_session, user, "google", "boom@example.com")
        pt = _make_provider_task(title="Survives")

        manager = _FakeTaskManager(
            tasks_by_email={"ok@example.com": [pt]},
            fail_emails={"boom@example.com"},
        )
        summary = await sync_all_task_accounts(db_session, user.id, manager)

        assert summary == {"accounts": 2, "upserted": 1, "failed": 1}
        result = await db_session.execute(select(Task).where(Task.user_id == user.id))
        task = result.scalar_one()
        assert task.title == "Survives"

    async def test_no_accounts_returns_zero_summary(self, db_session: AsyncSession) -> None:
        user = await _create_user(db_session)
        manager = _FakeTaskManager(tasks_by_email={})
        summary = await sync_all_task_accounts(db_session, user.id, manager)
        assert summary == {"accounts": 0, "upserted": 0, "failed": 0}


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
