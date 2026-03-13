"""Tests for chat tool definitions and handlers."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select

from underway.chat.tools import (
    MUTATING_TOOLS,
    TOOL_DEFINITIONS,
    execute_tool,
)
from underway.models.task import Task
from underway.models.user import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Tool definition tests
# ---------------------------------------------------------------------------


class TestToolDefinitions:
    def test_all_five_tools_defined(self) -> None:
        names = {t["function"]["name"] for t in TOOL_DEFINITIONS}
        assert names == {"get_tasks", "complete_task", "create_task", "update_task", "get_calendar"}

    def test_each_tool_has_function_type(self) -> None:
        for tool in TOOL_DEFINITIONS:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "parameters" in tool["function"]

    def test_mutating_tools_correct(self) -> None:
        assert {"complete_task", "create_task", "update_task"} == MUTATING_TOOLS

    def test_mutating_tools_excludes_read_only(self) -> None:
        assert "get_tasks" not in MUTATING_TOOLS
        assert "get_calendar" not in MUTATING_TOOLS


# ---------------------------------------------------------------------------
# Helper to create a user + tasks
# ---------------------------------------------------------------------------


async def _make_user(session: AsyncSession, email: str = "tools@test.com") -> User:
    user = User(app_login=email)
    user.id = uuid.uuid4()
    session.add(user)
    await session.flush()
    return user


async def _make_task(
    session: AsyncSession,
    user_id: uuid.UUID,
    title: str = "Test task",
    status: str = "active",
    list_type: str = "unprioritized",
    position: int = 0,
    priority: int | None = None,
) -> Task:
    task = Task(
        id=uuid.uuid4(),
        user_id=user_id,
        provider="google",
        provider_task_id=str(uuid.uuid4()),
        title=title,
        status=status,
        list_type=list_type,
        position=position,
        priority=priority,
        content_hash="abc",
    )
    session.add(task)
    await session.flush()
    return task


# ---------------------------------------------------------------------------
# Handler tests
# ---------------------------------------------------------------------------


class TestGetTasks:
    async def test_returns_user_tasks(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "gettasks1@test.com")
        await _make_task(db_session, user.id, title="Task A")
        await _make_task(db_session, user.id, title="Task B")

        result = await execute_tool("get_tasks", {}, user.id, db_session)
        assert result["success"] is True
        assert len(result["tasks"]) == 2

    async def test_filters_by_status(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "gettasks2@test.com")
        await _make_task(db_session, user.id, title="Active", status="active")
        await _make_task(db_session, user.id, title="Done", status="completed")

        result = await execute_tool("get_tasks", {"status": "active"}, user.id, db_session)
        assert result["success"] is True
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["title"] == "Active"

    async def test_filters_by_priority(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "gettasks3@test.com")
        await _make_task(db_session, user.id, title="High", priority=3)
        await _make_task(db_session, user.id, title="Low", priority=1)

        result = await execute_tool("get_tasks", {"priority": 3}, user.id, db_session)
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["title"] == "High"

    async def test_user_scoping(self, db_session: AsyncSession) -> None:
        user1 = await _make_user(db_session, "scope1@test.com")
        user2 = await _make_user(db_session, "scope2@test.com")
        await _make_task(db_session, user1.id, title="User1 task")
        await _make_task(db_session, user2.id, title="User2 task")

        result = await execute_tool("get_tasks", {}, user1.id, db_session)
        assert result["success"] is True
        assert len(result["tasks"]) == 1
        assert result["tasks"][0]["title"] == "User1 task"


class TestCompleteTask:
    async def test_completes_own_task(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "complete1@test.com")
        task = await _make_task(db_session, user.id, title="To complete")

        result = await execute_tool("complete_task", {"task_id": str(task.id)}, user.id, db_session)
        assert result["success"] is True
        assert result["task"]["status"] == "completed"

        # Verify in DB
        row = await db_session.execute(select(Task).where(Task.id == task.id))
        assert row.scalar_one().status == "completed"

    async def test_rejects_other_user_task(self, db_session: AsyncSession) -> None:
        owner = await _make_user(db_session, "owner@test.com")
        other = await _make_user(db_session, "other@test.com")
        task = await _make_task(db_session, owner.id, title="Owner only")

        result = await execute_tool("complete_task", {"task_id": str(task.id)}, other.id, db_session)
        assert "error" in result

    async def test_rejects_nonexistent_task(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "complete3@test.com")
        fake_id = str(uuid.uuid4())

        result = await execute_tool("complete_task", {"task_id": fake_id}, user.id, db_session)
        assert "error" in result

    async def test_rejects_invalid_uuid(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "complete4@test.com")

        result = await execute_tool("complete_task", {"task_id": "not-a-uuid"}, user.id, db_session)
        assert result["success"] is False
        assert "Invalid task ID" in result["error"]


class TestCreateTask:
    async def test_creates_task(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "create1@test.com")

        result = await execute_tool(
            "create_task",
            {"title": "New task", "description": "A description"},
            user.id,
            db_session,
        )
        assert result["success"] is True
        assert result["task"]["title"] == "New task"
        assert result["task"]["status"] == "active"

        # Verify in DB
        row = await db_session.execute(select(Task).where(Task.user_id == user.id))
        assert row.scalar_one().title == "New task"

    async def test_creates_task_with_priority(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "create2@test.com")

        result = await execute_tool(
            "create_task",
            {"title": "Prio task", "priority": 3},
            user.id,
            db_session,
        )
        assert result["success"] is True
        assert result["task"]["priority"] == 3


class TestUpdateTask:
    async def test_updates_task_fields(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "update1@test.com")
        task = await _make_task(db_session, user.id, title="Old title")

        result = await execute_tool(
            "update_task",
            {"task_id": str(task.id), "title": "New title", "priority": 2},
            user.id,
            db_session,
        )
        assert result["success"] is True
        assert result["task"]["title"] == "New title"
        assert result["task"]["priority"] == 2

    async def test_rejects_other_user_task(self, db_session: AsyncSession) -> None:
        owner = await _make_user(db_session, "upd-owner@test.com")
        other = await _make_user(db_session, "upd-other@test.com")
        task = await _make_task(db_session, owner.id, title="Owner task")

        result = await execute_tool(
            "update_task",
            {"task_id": str(task.id), "title": "Hacked"},
            other.id,
            db_session,
        )
        assert "error" in result

    async def test_rejects_invalid_uuid(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "update-invalid@test.com")

        result = await execute_tool(
            "update_task",
            {"task_id": "not-a-uuid", "title": "Nope"},
            user.id,
            db_session,
        )
        assert result["success"] is False
        assert "Invalid task ID" in result["error"]


class TestGetCalendar:
    async def test_returns_empty_events(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "calendar@test.com")

        result = await execute_tool("get_calendar", {}, user.id, db_session)
        assert result["events"] == []
        assert result["message"] == "No calendar connected."

    async def test_with_days_ahead(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "calendar2@test.com")

        result = await execute_tool("get_calendar", {"days_ahead": 14}, user.id, db_session)
        assert result["events"] == []
        assert "message" in result


class TestExecuteToolDispatcher:
    async def test_unknown_tool_returns_error(self, db_session: AsyncSession) -> None:
        user = await _make_user(db_session, "unknown@test.com")

        result = await execute_tool("nonexistent_tool", {}, user.id, db_session)
        assert "error" in result
        assert "Unknown tool" in result["error"]
