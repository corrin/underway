"""Read sources, compute a disposable queue, reconcile calendar-owned records."""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack
from datetime import UTC, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from underway.models.external_account import PROVIDER_TO_TASK, ExternalAccount
from underway.models.intentions import IntentionsRecord
from underway.providers.calendar.scheduling import RemoteEvent, SchedulingCalendar, connect_calendar
from underway.providers.task_manager import TaskManager
from underway.scheduling.planner import ancestors, build_week, rollups
from underway.scheduling.schemas import ActivityReport, CalendarBlock, Intentions, Snapshot, SourceActivity, SourceRef
from underway.scheduling.store import LocalIntentionsStore
from underway.services.task_sync import sync_provider_tasks

logger = logging.getLogger(__name__)
_locks: dict[UUID, asyncio.Lock] = {}


def reported_activity(events: list[RemoteEvent]) -> list[ActivityReport]:
    return [
        ActivityReport.model_validate(event.metadata["data"])
        for event in events
        if event.metadata.get("kind") == "activity"
    ]


def scheduled_block(event: RemoteEvent, now: datetime) -> CalendarBlock:
    block = CalendarBlock.model_validate(event.metadata["data"])
    return block.model_copy(
        update={
            "start": event.start,
            "end": event.end,
            "title": event.title,
            "protected": event.edited or event.start < now + timedelta(minutes=30),
        }
    )


class ScheduleService:
    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        self.session, self.user_id = session, user_id
        self.store = LocalIntentionsStore(session)

    async def _destination(self, intentions: Intentions, stack: AsyncExitStack) -> SchedulingCalendar:
        if not intentions.calendar_provider or not intentions.calendar_account:
            raise ValueError("Select a connected calendar account in intentions first.")
        else:
            account = await ExternalAccount.get_by_email_provider_and_user(
                self.session, intentions.calendar_account, intentions.calendar_provider, self.user_id
            )
        if account is None or not account.use_for_calendar or account.needs_reauth:
            raise ValueError("The selected calendar account is unavailable; reconnect it in Settings.")
        else:
            return await stack.enter_async_context(
                await connect_calendar(
                    self.session, self.user_id, intentions.calendar_provider, intentions.calendar_account
                )
            )

    async def _calendars(self, intentions: Intentions, calendar: SchedulingCalendar) -> Intentions:
        visible = {str(item["id"]): item for item in await calendar.calendars()}
        for identifier, kind in (
            (intentions.schedule_calendar_id, "schedule"),
            (intentions.activity_calendar_id, "activity"),
        ):
            if identifier is None:
                continue
            elif identifier not in visible:
                raise ValueError(
                    "A configured Underway calendar is missing. Restore it or clear its ID before rebuilding."
                )
            else:
                item = visible[identifier]
            if item.get("description") == f"underway:{kind}:v1" or item.get("name") == f"Underway - {kind}":
                pass
            else:
                raise ValueError("Suggestions and activity must use their dedicated Underway calendars.")
        if intentions.schedule_calendar_id and intentions.activity_calendar_id:
            return intentions
        else:
            schedule_id = intentions.schedule_calendar_id or await calendar.ensure_calendar(
                "schedule", intentions.timezone
            )
            activity_id = intentions.activity_calendar_id or await calendar.ensure_calendar(
                "activity", intentions.timezone
            )
            return await self.store.put(
                self.user_id,
                intentions.model_copy(
                    update={"schedule_calendar_id": schedule_id, "activity_calendar_id": activity_id}
                ),
            )

    async def _activities(self, intentions: Intentions) -> list[SourceActivity]:
        accounts = await ExternalAccount.get_accounts_for_user(self.session, self.user_id)
        manager = TaskManager()
        activities: list[SourceActivity] = []
        zone = ZoneInfo(intentions.timezone)
        for account in accounts:
            if not account.use_for_tasks:
                continue
            elif account.needs_reauth:
                raise ValueError(f"Task account {account.external_email} needs authentication; schedule retained.")
            else:
                provider = PROVIDER_TO_TASK.get(account.provider)
            if provider is None:
                raise ValueError(f"Unsupported task provider: {account.provider}")
            else:
                tasks = await manager.get_tasks(self.session, self.user_id, account.external_email, provider)
            async with self.session.begin_nested():
                await sync_provider_tasks(self.session, self.user_id, account.external_email, provider, tasks)
            for task in tasks:
                if task.status != "active":
                    continue
                else:
                    deadline = task.deadline
                if deadline is not None and deadline.tzinfo is None:
                    # Date-only source deadlines mean the end of that local date.
                    deadline = datetime.combine(deadline.date(), time.max, zone)
                else:
                    pass
                activities.append(
                    SourceActivity(
                        source=SourceRef.model_validate(
                            {
                                "provider": provider,
                                "account": account.external_email,
                                "container_id": task.project_id,
                                "task_id": task.provider_task_id or task.id,
                            }
                        ),
                        title=task.title,
                        description=task.description or "",
                        priority=task.priority,
                        parent_task_id=task.parent_id,
                        due=task.due_date,
                        deadline=deadline,
                        estimated_minutes=task.estimated_minutes,
                    )
                )
        available = {
            (activity.source.provider, activity.source.account, activity.source.container_id) for activity in activities
        }
        enabled = {
            (PROVIDER_TO_TASK.get(account.provider), account.external_email)
            for account in accounts
            if account.use_for_tasks
        }
        for node in intentions.nodes:
            for binding in node.sources:
                if (binding.provider, binding.account) not in enabled:
                    raise ValueError(f"{node.title}: bound source account is not connected for tasks.")
                elif (binding.provider, binding.account, binding.container_id) not in available:
                    # Empty source lists are valid: their repeatable parent remains selectable.
                    pass
                else:
                    pass
        return activities

    async def _snapshot(
        self, intentions: Intentions, calendar: SchedulingCalendar, stack: AsyncExitStack, now: datetime
    ) -> tuple[Snapshot, list[RemoteEvent]]:
        activities = await self._activities(intentions)
        end = max(
            [
                now + timedelta(days=7),
                *(activity.deadline for activity in activities if activity.deadline),
                *(node.deadline for node in intentions.nodes if node.deadline),
            ]
        )
        old = await calendar.events(
            intentions.schedule_calendar_id or "", intentions.timezone, now - timedelta(days=1), end
        )
        reports = reported_activity(await calendar.events(intentions.activity_calendar_id or "", intentions.timezone))
        preserved: list[CalendarBlock] = []
        busy: list[CalendarBlock] = []
        for event in old:
            if event.metadata.get("kind") == "schedule":
                block = scheduled_block(event, now)
                if block.protected and block.end > now:
                    preserved.append(block)
                else:
                    pass
            elif event.busy:
                busy.append(CalendarBlock(id=event.id, start=event.start, end=event.end, title=event.title))
            else:
                pass
        for account in await ExternalAccount.get_accounts_for_user(self.session, self.user_id):
            if not account.use_for_calendar:
                continue
            elif account.needs_reauth:
                raise ValueError(f"Calendar account {account.external_email} needs authentication; schedule retained.")
            elif account.provider not in ("google", "o365"):
                continue
            else:
                client = await stack.enter_async_context(
                    await connect_calendar(
                        self.session,
                        self.user_id,
                        "google" if account.provider == "google" else "o365",
                        account.external_email,
                    )
                )
            for source_calendar in await client.calendars():
                identifier = str(source_calendar["id"])
                if (
                    account.provider == intentions.calendar_provider
                    and account.external_email == intentions.calendar_account
                    and identifier in (intentions.schedule_calendar_id, intentions.activity_calendar_id)
                ):
                    continue
                else:
                    timezone = str(source_calendar.get("timeZone") or intentions.timezone)
                for event in await client.events(identifier, timezone, now - timedelta(days=1), end):
                    if event.busy:
                        busy.append(CalendarBlock(id=event.id, title=event.title, start=event.start, end=event.end))
                    else:
                        pass
        return Snapshot(
            intentions=intentions, activities=activities, reports=reports, preserved=preserved, busy=busy
        ), old

    async def rebuild(self) -> dict[str, Any]:
        async with _locks.setdefault(self.user_id, asyncio.Lock()):
            # Cross-worker serialization: the row lock covers source reads and calendar writes.
            record = await self.session.scalar(
                select(IntentionsRecord).where(IntentionsRecord.user_id == self.user_id).with_for_update()
            )
            intentions = await self.store.get(self.user_id)
            if not intentions.enabled:
                return {"published": False, "enabled": False, "blocks": [], "warnings": []}
            else:
                pass
            try:
                async with AsyncExitStack() as stack:
                    calendar = await self._destination(intentions, stack)
                    intentions = await self._calendars(intentions, calendar)
                    now = datetime.now(UTC)
                    snapshot, existing = await self._snapshot(intentions, calendar, stack, now)
                    plan = build_week(snapshot, now)
                    by_key = {
                        str(event.metadata["key"]): event
                        for event in existing
                        if event.metadata.get("kind") == "schedule"
                    }
                    wanted = {block.id for block in plan.blocks}
                    # Validate/compute everything first. Only replace events carrying our ownership record.
                    for block in plan.blocks:
                        if block.protected:
                            continue
                        else:
                            previous = by_key.get(block.id)
                        data = block.model_dump(mode="json")
                        if previous is not None and previous.metadata.get("data") == data:
                            continue
                        else:
                            await calendar.put_event(
                                intentions.schedule_calendar_id or "",
                                block.id,
                                "schedule",
                                block.title,
                                block.start,
                                block.end,
                                data,
                                previous.id if previous else None,
                                etag=previous.etag if previous else None,
                            )
                    for key, event in by_key.items():
                        if key not in wanted and event.start >= now + timedelta(minutes=30) and not event.edited:
                            await calendar.delete_event(
                                intentions.schedule_calendar_id or "", event.id, etag=event.etag
                            )
                        else:
                            pass
                    if record:
                        record.last_error = None
                        record.last_warnings = plan.warnings
                        record.last_published = now.replace(tzinfo=None)
                    else:
                        pass
                    return {
                        "published": True,
                        "enabled": True,
                        **plan.model_dump(mode="json"),
                        "progress": [
                            progress.model_dump()
                            for progress in rollups(snapshot, now.astimezone(ZoneInfo(intentions.timezone)).date())
                        ],
                    }
            except Exception:
                logger.exception("Schedule rebuild failed for user %s", self.user_id)
                message = (
                    "Schedule refresh failed; publication may be partial. Confirmed activity is saved. "
                    "Check connected sources and retry to reconcile the schedule."
                )
                if record:
                    record.last_error = message
                else:
                    pass
                return {"published": False, "enabled": True, "error": message}

    async def current(self) -> dict[str, Any]:
        intentions = await self.store.get(self.user_id)
        record = await self.session.get(IntentionsRecord, self.user_id)
        result: dict[str, Any] = {
            "enabled": intentions.enabled,
            "blocks": [],
            "progress": [],
            "error": record.last_error if record else None,
            "warnings": record.last_warnings if record else [],
            "last_published": record.last_published.isoformat() if record and record.last_published else None,
        }
        if not intentions.schedule_calendar_id or not intentions.activity_calendar_id:
            return result
        else:
            now = datetime.now(UTC)
        async with AsyncExitStack() as stack:
            calendar = await self._destination(intentions, stack)
            events = await calendar.events(
                intentions.schedule_calendar_id, intentions.timezone, now - timedelta(days=1), now + timedelta(days=7)
            )
            result["blocks"] = [
                scheduled_block(event, now).model_dump(mode="json")
                for event in events
                if event.metadata.get("kind") == "schedule" and event.end > now
            ]
            reports = reported_activity(await calendar.events(intentions.activity_calendar_id, intentions.timezone))
            result["reports"] = [report.model_dump(mode="json") for report in reports]
            snapshot = Snapshot(intentions=intentions, reports=reports)
            result["progress"] = [
                row.model_dump() for row in rollups(snapshot, now.astimezone(ZoneInfo(intentions.timezone)).date())
            ]
        return result

    async def report(self, report: ActivityReport, replace: bool = False) -> dict[str, Any]:
        async with _locks.setdefault(self.user_id, asyncio.Lock()):
            await self.session.scalar(
                select(IntentionsRecord).where(IntentionsRecord.user_id == self.user_id).with_for_update()
            )
            intentions = await self.store.get(self.user_id)
            nodes = {node.id: node for node in intentions.nodes}
            if report.node_id not in nodes:
                raise ValueError("Choose an existing intention node for this activity report.")
            else:
                path = ancestors(nodes, report.node_id)
            if any(node_id not in path or not nodes[node_id].interval_days for node_id in report.fulfilled_intentions):
                raise ValueError("A cadence occurrence must belong to this node or one of its ancestors.")
            else:
                zone = ZoneInfo(intentions.timezone)
            if report.date > datetime.now(zone).date():
                raise ValueError("Future calendar reservations cannot be recorded as actual activity.")
            else:
                pass
            async with AsyncExitStack() as stack:
                calendar = await self._destination(intentions, stack)
                intentions = await self._calendars(intentions, calendar)
                events = await calendar.events(intentions.activity_calendar_id or "", intentions.timezone)
                previous = next(
                    (
                        event
                        for event in events
                        if event.metadata.get("kind") == "activity" and event.metadata.get("key") == report.id
                    ),
                    None,
                )
                data = report.model_dump(mode="json")
                if previous is not None and not replace and previous.metadata.get("data") != data:
                    raise ValueError("This report ID is already saved. Use an explicit correction to replace it.")
                elif previous is None and replace:
                    raise ValueError("The report to correct does not exist.")
                else:
                    pass
                start = datetime.combine(report.date, time.min, zone)
                if previous is None or previous.metadata.get("data") != data:
                    await calendar.put_event(
                        intentions.activity_calendar_id or "",
                        report.id,
                        "activity",
                        f"{nodes[report.node_id].title}: {report.minutes or 'duration unknown'} minutes reported",
                        start,
                        start + timedelta(days=1),
                        data,
                        previous.id if previous else None,
                        all_day=report.date,
                        etag=previous.etag if previous else None,
                    )
                else:
                    pass
        # Replanning is separate: a subsequent scheduling failure does not undo an acknowledged report.
        return {"saved": True, "report": data, "schedule": await self.rebuild()}


async def scheduling_loop(factory: async_sessionmaker[AsyncSession]) -> None:
    while True:
        try:
            async with factory() as session:
                user_ids = list((await session.scalars(select(IntentionsRecord.user_id))).all())
            for user_id in user_ids:
                try:
                    async with factory() as session:
                        await ScheduleService(session, user_id).rebuild()
                        await session.commit()
                except Exception:
                    logger.exception("Scheduled refresh failed for user %s", user_id)
        except Exception:
            logger.exception("Scheduler polling failed")
        await asyncio.sleep(15 * 60)
