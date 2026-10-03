"""Provider contract tests without live calendar writes."""

import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from underway.providers.calendar.scheduling import MARKER, SchedulingCalendar

NOW = datetime(2026, 10, 5, 9, tzinfo=UTC)


async def test_google_pagination_and_free_events() -> None:
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        item = {
            "id": "one",
            "summary": "Busy",
            "start": {"dateTime": NOW.isoformat()},
            "end": {"dateTime": (NOW + timedelta(hours=1)).isoformat()},
        }
        if "pageToken" in request.url.params:
            item.update(id="two", transparency="transparent")
            return httpx.Response(200, json={"items": [item]})
        else:
            return httpx.Response(200, json={"items": [item], "nextPageToken": "next"})

    async with SchedulingCalendar("google", "token", httpx.MockTransport(handle)) as client:
        events = await client.events("cal", "UTC", NOW, NOW + timedelta(days=7))
    assert [event.busy for event in events] == [True, False]
    assert calls[1].url.params["pageToken"] == "next"
    assert calls[1].url.params["timeMin"] == NOW.isoformat()


async def test_google_retry_recovers_acknowledged_create_without_duplicate() -> None:
    writes: list[dict[str, object]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            writes.append(json.loads(request.content))
            return httpx.Response(409, json={"error": "already exists"})
        elif request.method == "GET":
            return httpx.Response(200, json=writes[0])
        else:
            raise AssertionError("A create retry must not overwrite an existing event")

    async with SchedulingCalendar("google", "token", httpx.MockTransport(handle)) as client:
        identifier = await client.put_event(
            "cal", "report", "activity", "Friends", NOW, NOW + timedelta(days=1), {"minutes": 60}, all_day=NOW.date()
        )
    assert identifier == writes[0]["id"]
    assert len(writes) == 1
    assert writes[0]["transparency"] == "transparent"
    assert writes[0]["start"] == {"date": "2026-10-05"}


async def test_graph_metadata_roundtrip_and_transaction_identity() -> None:
    bodies: list[dict[str, object]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        assert 'outlook.body-content-type="text"' in request.headers["Prefer"]
        if request.method == "POST":
            bodies.append(json.loads(request.content))
            return httpx.Response(201, json={"id": "remote"})
        else:
            return httpx.Response(200, json={"value": [{**bodies[0], "id": "remote"}]})

    async with SchedulingCalendar("o365", "token", httpx.MockTransport(handle)) as client:
        for _ in range(2):
            await client.put_event(
                "cal", "slot", "schedule", "Friends", NOW, NOW + timedelta(hours=1), {"node_id": "friends"}
            )
        events = await client.events("cal", "UTC", NOW, NOW + timedelta(days=7))
    assert bodies[0]["transactionId"] == bodies[1]["transactionId"]
    assert events[0].metadata["data"] == {"node_id": "friends"}
    assert not events[0].edited
    events[0].start += timedelta(minutes=15)
    assert events[0].edited


async def test_failed_page_is_not_returned_as_partial_success() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if "pageToken" in request.url.params:
            return httpx.Response(503)
        else:
            return httpx.Response(200, json={"items": [{"id": "first"}], "nextPageToken": "next"})

    async with SchedulingCalendar("google", "token", httpx.MockTransport(handle)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.calendars()


async def test_unknown_metadata_is_not_owned() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "user",
                        "start": {"date": "2026-10-05"},
                        "end": {"date": "2026-10-06"},
                        "description": "Edited" + MARKER + "invalid",
                    }
                ]
            },
        )

    async with SchedulingCalendar("google", "token", httpx.MockTransport(handle)) as client:
        events = await client.events("cal", "Pacific/Auckland")
    assert events[0].metadata == {}
    assert events[0].busy
    assert events[0].start.utcoffset() == timedelta(hours=13)


async def test_concurrent_user_edit_rejects_stale_publication() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.headers["If-Match"] == '"read-version"'
        return httpx.Response(412)

    async with SchedulingCalendar("google", "token", httpx.MockTransport(handle)) as client:
        with pytest.raises(httpx.HTTPStatusError):
            await client.put_event(
                "cal",
                "slot",
                "schedule",
                "Friends",
                NOW,
                NOW + timedelta(hours=1),
                {},
                existing_id="remote",
                etag='"read-version"',
            )
        with pytest.raises(httpx.HTTPStatusError):
            await client.delete_event("cal", "remote", etag='"read-version"')


async def test_create_retry_does_not_overwrite_corrected_activity() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(409)
        elif request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "summary": "Corrected report",
                    "extendedProperties": {"private": {"underwayKey": "report", "underwayKind": "activity"}},
                },
            )
        else:
            raise AssertionError("Retry attempted to overwrite a correction")

    async with SchedulingCalendar("google", "token", httpx.MockTransport(handle)) as client:
        with pytest.raises(ValueError, match="different data"):
            await client.put_event(
                "cal",
                "report",
                "activity",
                "Original",
                NOW,
                NOW + timedelta(days=1),
                {"minutes": 60},
                all_day=NOW.date(),
            )
