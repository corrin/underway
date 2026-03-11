"""Task sync service — syncs provider tasks to the database."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from underway.models.task import Task
from underway.providers.task_provider import ProviderTask

logger = logging.getLogger(__name__)


async def sync_provider_tasks(
    session: AsyncSession,
    user_id: UUID,
    task_user_email: str,
    provider_name: str,
    provider_tasks: list[ProviderTask],
) -> int:
    """Sync tasks from a provider to the database.

    Returns the number of tasks created or updated.
    """
    logger.info(
        "Syncing %d tasks from %s for user_id=%s",
        len(provider_tasks),
        provider_name,
        user_id,
    )

    updated_count = 0

    for pt in provider_tasks:
        created_or_updated = await _create_or_update_task(session, user_id, task_user_email, provider_name, pt)
        if created_or_updated:
            updated_count += 1

    # Clean up deleted tasks
    deleted = await sync_task_deletions(
        session,
        user_id,
        provider_name,
        [pt.id for pt in provider_tasks],
    )

    logger.info(
        "Sync complete for %s: %d upserted, %d deleted",
        provider_name,
        updated_count,
        deleted,
    )
    return updated_count


async def _create_or_update_task(
    session: AsyncSession,
    user_id: UUID,
    task_user_email: str,
    provider_name: str,
    provider_task: ProviderTask,
) -> bool:
    """Create or update a single task from provider data. Returns True if changed."""
    content_hash = _compute_hash(provider_task)

    result = await session.execute(
        select(Task).where(
            Task.user_id == user_id,
            Task.provider == provider_name,
            Task.provider_task_id == provider_task.id,
        )
    )
    existing = result.scalar_one_or_none()

    if not existing:
        task = Task(
            user_id=user_id,
            task_user_email=task_user_email,
            provider=provider_name,
            provider_task_id=provider_task.id,
            title=provider_task.title,
            status=provider_task.status,
            due_date=provider_task.due_date,
            priority=provider_task.priority,
            project_id=provider_task.project_id,
            project_name=provider_task.project_name,
            parent_id=provider_task.parent_id,
            section_id=provider_task.section_id,
            content_hash=content_hash,
            list_type="unprioritized",
            position=0,
        )
        session.add(task)
        return True

    if existing.content_hash == content_hash:
        return False  # unchanged

    existing.title = provider_task.title
    existing.status = provider_task.status
    existing.due_date = provider_task.due_date
    existing.priority = provider_task.priority
    existing.project_id = provider_task.project_id
    existing.project_name = provider_task.project_name
    existing.parent_id = provider_task.parent_id
    existing.section_id = provider_task.section_id
    existing.content_hash = content_hash
    existing.last_synced = datetime.now(UTC)
    existing.task_user_email = task_user_email
    return True


async def sync_task_deletions(
    session: AsyncSession,
    user_id: UUID,
    provider: str,
    current_provider_task_ids: list[str],
) -> int:
    """Remove tasks no longer present in the provider. Returns count deleted."""
    result = await session.execute(
        delete(Task)
        .where(
            Task.user_id == user_id,
            Task.provider == provider,
            Task.provider_task_id.notin_(current_provider_task_ids),
        )
        .returning(Task.id)
    )
    deleted_ids = list(result.scalars().all())
    return len(deleted_ids)


def _compute_hash(provider_task: ProviderTask) -> str:
    """Compute a content hash for change detection."""
    content = {
        "title": provider_task.title,
        "status": provider_task.status,
        "due_date": (provider_task.due_date.isoformat() if provider_task.due_date else None),
        "priority": provider_task.priority,
        "project_id": provider_task.project_id,
        "parent_id": provider_task.parent_id,
        "section_id": provider_task.section_id,
    }
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
