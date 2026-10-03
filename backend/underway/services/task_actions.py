"""Acknowledge source edits only after the provider accepts them."""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from underway.models.task import Task
from underway.providers.task_manager import TaskManager
from underway.scheduling.service import ScheduleService
from underway.services.task_sync import sync_provider_tasks


async def edit_task(session: AsyncSession, task: Task, changes: dict[str, Any]) -> dict[str, Any]:
    if "status" in changes and changes["status"] not in ("active", "completed"):
        raise ValueError("Status must be active or completed.")
    else:
        pass
    user_id = task.user_id
    if task.provider == "local":
        for key, value in changes.items():
            setattr(task, key, value)
        if task.status == "completed":
            task.list_type = "completed"
        elif task.list_type == "completed":
            task.list_type = "unprioritized"
        else:
            pass
        await session.flush()
        result: dict[str, Any] = {"success": True, "task": task.to_dict()}
    else:
        manager = TaskManager()
        provider = manager.get_provider(task.provider)
        if task.provider == "google_tasks" and "priority" in changes:
            raise ValueError("Google Tasks does not support priority changes.")
        else:
            accepted = await provider.update_task(session, user_id, str(task.id), changes)
        if not accepted:
            raise ValueError("The source did not accept the task update.")
        else:
            result = {"success": True, "source_updated": True}
        try:
            tasks = await provider.get_tasks(session, user_id, task.task_user_email or "")
            async with session.begin_nested():
                await sync_provider_tasks(session, user_id, task.task_user_email or "", task.provider, tasks)
        except Exception:
            # The write was acknowledged; do not invite a second completion of a recurring task.
            result["warning"] = "Source edit succeeded but refresh failed. Refresh before making another edit."
    result["schedule"] = await ScheduleService(session, user_id).rebuild()
    return result
