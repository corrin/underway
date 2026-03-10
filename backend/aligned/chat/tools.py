"""Chat tool definitions and async handler functions for OpenAI function-calling."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from aligned.models.task import Task

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    _ToolHandler = Callable[[dict[str, Any], uuid.UUID, AsyncSession], Awaitable[dict[str, Any]]]

# ---------------------------------------------------------------------------
# Tool definitions (OpenAI function-calling format)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_tasks",
            "description": "List the user's tasks, optionally filtered by status or priority.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed"],
                        "description": "Filter tasks by status.",
                    },
                    "priority": {
                        "type": "integer",
                        "enum": [1, 2, 3, 4],
                        "description": "Filter tasks by priority (1=low, 2=medium, 3=high, 4=urgent).",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a task as completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The UUID of the task to complete.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "The title of the task.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional description of the task.",
                    },
                    "priority": {
                        "type": "integer",
                        "enum": [1, 2, 3, 4],
                        "description": "Priority level (1=low, 2=medium, 3=high, 4=urgent).",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_task",
            "description": "Update fields on an existing task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The UUID of the task to update.",
                    },
                    "title": {
                        "type": "string",
                        "description": "New title for the task.",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description for the task.",
                    },
                    "priority": {
                        "type": "integer",
                        "enum": [1, 2, 3, 4],
                        "description": "New priority (1=low, 2=medium, 3=high, 4=urgent).",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "completed"],
                        "description": "New status for the task.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_calendar",
            "description": "Retrieve calendar events for the user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days ahead to fetch events (default: 7).",
                    },
                },
                "required": [],
            },
        },
    },
]

# Tools that mutate data (used for confirmation flows, guardrails, etc.)
MUTATING_TOOLS: set[str] = {"complete_task", "create_task", "update_task"}

# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------


async def _handle_get_tasks(
    arguments: dict[str, Any],
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Retrieve tasks for the user, with optional filters."""
    stmt = select(Task).where(Task.user_id == user_id)

    status = arguments.get("status")
    if status is not None:
        stmt = stmt.where(Task.status == status)

    priority = arguments.get("priority")
    if priority is not None:
        stmt = stmt.where(Task.priority == priority)

    stmt = stmt.order_by(Task.position)
    result = await session.execute(stmt)
    tasks = list(result.scalars().all())
    return {"success": True, "tasks": [t.to_dict() for t in tasks]}


async def _handle_complete_task(
    arguments: dict[str, Any],
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Mark a task as completed, only if it belongs to the user."""
    task_id = arguments["task_id"]
    try:
        parsed_id = uuid.UUID(task_id)
    except ValueError:
        return {"success": False, "error": f"Invalid task ID: {task_id}"}
    result = await session.execute(select(Task).where(Task.id == parsed_id, Task.user_id == user_id))
    task = result.scalar_one_or_none()
    if task is None:
        return {"error": "Task not found or access denied"}

    task.status = "completed"
    await session.flush()
    return {"success": True, "task": task.to_dict()}


async def _handle_create_task(
    arguments: dict[str, Any],
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Create a new task for the user."""
    task = Task(
        id=uuid.uuid4(),
        user_id=user_id,
        provider="chat",
        provider_task_id=str(uuid.uuid4()),
        title=arguments["title"],
        description=arguments.get("description"),
        priority=arguments.get("priority"),
        status="active",
        list_type="unprioritized",
        position=0,
        content_hash="",
    )
    session.add(task)
    await session.flush()
    return {"success": True, "task": task.to_dict()}


async def _handle_update_task(
    arguments: dict[str, Any],
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Update fields on an existing task belonging to the user."""
    task_id = arguments["task_id"]
    try:
        parsed_id = uuid.UUID(task_id)
    except ValueError:
        return {"success": False, "error": f"Invalid task ID: {task_id}"}
    result = await session.execute(select(Task).where(Task.id == parsed_id, Task.user_id == user_id))
    task = result.scalar_one_or_none()
    if task is None:
        return {"error": "Task not found or access denied"}

    updatable = ("title", "description", "priority", "status")
    for field in updatable:
        if field in arguments:
            setattr(task, field, arguments[field])

    await session.flush()
    return {"success": True, "task": task.to_dict()}


async def _handle_get_calendar(
    arguments: dict[str, Any],
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Stub: return empty events list. Calendar integration deferred."""
    _ = arguments, user_id, session  # unused for now
    return {"events": [], "message": "Calendar not connected yet."}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TOOL_HANDLERS: dict[str, _ToolHandler] = {
    "get_tasks": _handle_get_tasks,
    "complete_task": _handle_complete_task,
    "create_task": _handle_create_task,
    "update_task": _handle_update_task,
    "get_calendar": _handle_get_calendar,
}


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    user_id: uuid.UUID,
    session: AsyncSession,
) -> dict[str, Any]:
    """Dispatch a tool call to the appropriate handler."""
    handler = _TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"Unknown tool: {tool_name}"}
    result: dict[str, Any] = await handler(arguments, user_id, session)
    return result
