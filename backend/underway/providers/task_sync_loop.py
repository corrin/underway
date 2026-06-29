"""Background loop that periodically syncs provider tasks into the combined list."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from underway.models.external_account import ExternalAccount
from underway.providers.task_manager import TaskManager
from underway.services.task_sync import sync_all_task_accounts

logger = logging.getLogger(__name__)

TASK_SYNC_INTERVAL_SECONDS = 15 * 60  # 15 minutes


async def sync_all_users(
    session_factory: async_sessionmaker[AsyncSession],
    task_manager: TaskManager,
) -> None:
    """Sync every user that has task-enabled accounts. One pass; resilient per user."""
    async with session_factory() as session:
        user_ids = await ExternalAccount.get_user_ids_with_task_accounts(session)

    for user_id in user_ids:
        try:
            async with session_factory() as session:
                summary = await sync_all_task_accounts(session, user_id, task_manager)
                await session.commit()
            logger.info("Task sync for user_id=%s: %s", user_id, summary)
        except Exception:
            logger.exception("Task sync loop failed for user_id=%s", user_id)


async def task_sync_loop(session_factory: async_sessionmaker[AsyncSession]) -> None:
    """Background loop that syncs provider tasks for all users every interval."""
    logger.info("Starting task sync background loop")
    task_manager = TaskManager()
    while True:
        try:
            await sync_all_users(session_factory, task_manager)
        except Exception:
            logger.exception("Error in task sync loop")
        await asyncio.sleep(TASK_SYNC_INTERVAL_SECONDS)
