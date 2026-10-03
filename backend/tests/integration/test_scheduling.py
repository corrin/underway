"""Scheduling authorization, recovery, and acknowledgement boundaries."""

from datetime import UTC, datetime, time, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from underway.auth.jwt import create_access_token
from underway.models.user import User
from underway.providers.calendar.scheduling import RemoteEvent, SchedulingCalendar, fingerprint
from underway.scheduling.schemas import ActivityReport, CalendarBlock, IntentionNode, Intentions, Snapshot, Window
from underway.scheduling.service import ScheduleService, scheduled_block
from underway.scheduling.store import LocalIntentionsStore


async def setup_service(session: AsyncSession) -> tuple[ScheduleService, Intentions]:
    user = User(id=uuid4(), app_login="queue@example.com")
    session.add(user)
    await session.flush()
    document = Intentions(
        enabled=True,
        timezone="UTC",
        calendar_provider="google",
        calendar_account="me",
        schedule_calendar_id="suggestions",
        activity_calendar_id="actuals",
        nodes=[IntentionNode(id="friends", title="Friends", interval_days=7)],
        allowed_windows=[Window(weekdays=list(range(7)), start=time(9), end=time(12))],
    )
    service = ScheduleService(session, user.id)
    return service, await service.store.put(user.id, document)


async def test_store_revision_roundtrip_and_user_isolation(db_session: AsyncSession) -> None:
    service, document = await setup_service(db_session)
    restored = Intentions.model_validate_json(document.model_dump_json())
    assert restored == await service.store.get(service.user_id)
    restored.nodes[0].title = "Catch-ups"
    await service.store.put(service.user_id, restored)
    with pytest.raises(ValueError, match="changed"):
        await service.store.put(service.user_id, document)
    assert (await LocalIntentionsStore(db_session).get(uuid4())).nodes == []


async def test_source_failure_never_changes_published_events(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _ = await setup_service(db_session)
    calendar = AsyncMock(spec=SchedulingCalendar)
    calendar.calendars.return_value = [
        {"id": "suggestions", "description": "underway:schedule:v1"},
        {"id": "actuals", "description": "underway:activity:v1"},
    ]
    monkeypatch.setattr(service, "_destination", AsyncMock(return_value=calendar))
    monkeypatch.setattr(service, "_snapshot", AsyncMock(side_effect=RuntimeError("source down")))
    result = await service.rebuild()
    assert not result["published"]
    calendar.put_event.assert_not_awaited()
    calendar.delete_event.assert_not_awaited()


async def test_rebuild_retry_reuses_calendar_identity(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, document = await setup_service(db_session)
    calendar = AsyncMock(spec=SchedulingCalendar)
    calendar.calendars.return_value = [
        {"id": "suggestions", "description": "underway:schedule:v1"},
        {"id": "actuals", "description": "underway:activity:v1"},
    ]
    now = datetime.now(UTC)
    block = CalendarBlock(
        id="slot", title="Friends", node_id="friends", start=now + timedelta(hours=2), end=now + timedelta(hours=3)
    )
    event = RemoteEvent(
        id="remote",
        title=block.title,
        start=block.start,
        end=block.end,
        metadata={
            "kind": "schedule",
            "key": block.id,
            "data": block.model_dump(mode="json"),
            "fingerprint": fingerprint(block.title, block.start, block.end),
        },
    )
    document.allowed_windows = [Window(weekdays=[0], start=time(9), end=time(9, 30))]
    state = Snapshot(intentions=document, preserved=[block.model_copy(update={"protected": True})])
    monkeypatch.setattr(service, "_destination", AsyncMock(return_value=calendar))
    monkeypatch.setattr(service, "_snapshot", AsyncMock(return_value=(state, [event])))
    for _ in range(2):
        assert (await service.rebuild())["published"]
    calendar.put_event.assert_not_awaited()
    calendar.delete_event.assert_not_awaited()


async def test_report_acknowledgement_survives_rebuild_failure_and_retries(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    service, _ = await setup_service(db_session)
    calendar = AsyncMock(spec=SchedulingCalendar)
    calendar.calendars.return_value = [
        {"id": "suggestions", "description": "underway:schedule:v1"},
        {"id": "actuals", "description": "underway:activity:v1"},
    ]
    calendar.events.return_value = []
    monkeypatch.setattr(service, "_destination", AsyncMock(return_value=calendar))
    monkeypatch.setattr(service, "rebuild", AsyncMock(return_value={"published": False, "error": "offline"}))
    report = ActivityReport(
        id="stable-report",
        node_id="friends",
        date=datetime.now(UTC).date(),
        minutes=45,
        fulfilled_intentions=["friends"],
    )
    result = await service.report(report)
    assert result["saved"]
    assert not result["schedule"]["published"]
    args = calendar.put_event.await_args.args
    calendar.events.return_value = [
        RemoteEvent(
            id="remote",
            title=args[3],
            start=args[4],
            end=args[5],
            metadata={"kind": "activity", "key": report.id, "data": args[6]},
        )
    ]
    assert (await service.report(report))["saved"]
    assert calendar.put_event.await_count == 1
    report.minutes = 60
    with pytest.raises(ValueError, match="explicit correction"):
        await service.report(report)
    assert (await service.report(report, replace=True))["saved"]
    assert calendar.put_event.await_count == 2
    assert calendar.put_event.await_args.args[7] == "remote"


def test_user_edits_and_imminent_blocks_are_preserved() -> None:
    now = datetime.now(UTC)
    block = CalendarBlock(id="slot", title="Friends", start=now + timedelta(hours=2), end=now + timedelta(hours=3))
    event = RemoteEvent(
        id="remote",
        title=block.title,
        start=block.start,
        end=block.end,
        metadata={
            "data": block.model_dump(mode="json"),
            "fingerprint": fingerprint(block.title, block.start, block.end),
        },
    )
    assert not scheduled_block(event, now).protected
    event.title = "My chosen friend"
    assert scheduled_block(event, now).protected
    event.title = block.title
    assert scheduled_block(event, now + timedelta(hours=2)).protected


async def test_routes_require_auth_and_reject_stale_import(client: AsyncClient, db_session: AsyncSession) -> None:
    assert (await client.get("/api/intentions")).status_code == 401
    assert (await client.post("/api/schedule/rebuild")).status_code == 401
    assert (await client.post("/api/activity", json={})).status_code == 401
    user = User(id=uuid4(), app_login="routes@example.com")
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(user.id, user.app_login, "test-secret-key-at-least-32-chars!")
    headers = {"Authorization": f"Bearer {token}"}
    document = (await client.get("/api/intentions", headers=headers)).json()
    result = await client.put("/api/intentions", headers=headers, json=document)
    assert result.status_code == 200
    assert result.json()["intentions"]["revision"] == 1
    assert (await client.put("/api/intentions", headers=headers, json=document)).status_code == 409
    document["timezone"] = "invalid/timezone"
    assert (await client.put("/api/intentions", headers=headers, json=document)).status_code == 422
