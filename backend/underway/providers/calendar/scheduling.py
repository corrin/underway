"""Strict, paginated calendar operations for the scheduler and its activity ledger."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, cast
from urllib.parse import quote
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from underway.providers.calendar.google import GoogleCalendarProvider
from underway.providers.calendar.o365 import O365CalendarProvider

MARKER = "\n\n[underway:v1]\n"


class RemoteEvent(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    busy: bool = True
    etag: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def edited(self) -> bool:
        expected = self.metadata.get("fingerprint")
        return bool(expected and expected != fingerprint(self.title, self.start, self.end))


def fingerprint(title: str, start: datetime, end: datetime) -> str:
    raw = [title, start.astimezone(UTC).isoformat(), end.astimezone(UTC).isoformat()]
    return hashlib.sha256(json.dumps(raw).encode()).hexdigest()


def event_datetime(value: dict[str, Any], fallback_zone: str) -> datetime:
    if value.get("date"):
        return datetime.fromisoformat(str(value["date"])).replace(tzinfo=ZoneInfo(fallback_zone))
    else:
        parsed = datetime.fromisoformat(str(value["dateTime"]).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        zone_name = str(value.get("timeZone", fallback_zone))
        # Graph requests below explicitly request UTC rather than Windows timezone names.
        parsed = parsed.replace(tzinfo=ZoneInfo(zone_name))
    else:
        pass
    return parsed


class SchedulingCalendar:
    def __init__(
        self,
        provider: Literal["google", "o365"],
        token: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.provider = provider
        self.base = (
            "https://www.googleapis.com/calendar/v3" if provider == "google" else "https://graph.microsoft.com/v1.0"
        )
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {token}",
                "Prefer": 'outlook.timezone="UTC", IdType="ImmutableId", outlook.body-content-type="text"',
            },
            timeout=30,
            transport=transport,
        )

    async def __aenter__(self) -> SchedulingCalendar:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.client.aclose()

    async def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
        etag: str | None = None,
    ) -> dict[str, Any]:
        url = path if path.startswith("https://") else self.base + path
        if not url.startswith(self.base + "/"):
            raise ValueError("Unexpected calendar pagination host.")
        else:
            response = await self.client.request(
                method, url, json=body, params=params, headers={"If-Match": etag} if etag else None
            )
        response.raise_for_status()
        return cast(dict[str, Any], response.json()) if response.content else {}

    async def pages(self, path: str, params: dict[str, str] | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        params = dict(params or {})
        while True:
            response = await self.request("GET", path, params=params)
            items.extend(response.get("items" if self.provider == "google" else "value", []))
            token = response.get("nextPageToken") if self.provider == "google" else response.get("@odata.nextLink")
            if not token:
                break
            elif token in seen:
                raise ValueError("Repeated calendar pagination cursor.")
            else:
                seen.add(token)
            if self.provider == "google":
                params["pageToken"] = token
            else:
                path, params = token, {}
        return items

    async def calendars(self) -> list[dict[str, Any]]:
        return await self.pages("/users/me/calendarList" if self.provider == "google" else "/me/calendars")

    async def ensure_calendar(self, kind: Literal["schedule", "activity"], timezone: str) -> str:
        marker = f"underway:{kind}:v1"
        for calendar in await self.calendars():
            if calendar.get("description") == marker or calendar.get("name") == f"Underway - {kind}":
                return str(calendar["id"])
            else:
                pass
        if self.provider == "google":
            created = await self.request(
                "POST", "/calendars", {"summary": f"Underway - {kind}", "description": marker, "timeZone": timezone}
            )
        else:
            created = await self.request("POST", "/me/calendars", {"name": f"Underway - {kind}"})
        return str(created["id"])

    def events_path(self, calendar_id: str) -> str:
        quoted = quote(calendar_id, safe="")
        return f"/calendars/{quoted}/events" if self.provider == "google" else f"/me/calendars/{quoted}/events"

    async def events(
        self, calendar_id: str, timezone: str, start: datetime | None = None, end: datetime | None = None
    ) -> list[RemoteEvent]:
        path = self.events_path(calendar_id)
        if self.provider == "google":
            params = {"maxResults": "2500", "singleEvents": "true"}
            if start is not None and end is not None:
                params.update(timeMin=start.isoformat(), timeMax=end.isoformat())
            else:
                pass
        else:
            params = {"$top": "250"}
            if start is not None and end is not None:
                path = path.removesuffix("events") + "calendarView"
                params.update(startDateTime=start.isoformat(), endDateTime=end.isoformat())
            else:
                pass
        result: list[RemoteEvent] = []
        for item in await self.pages(path, params):
            if item.get("status") == "cancelled" or item.get("isCancelled"):
                continue
            else:
                pass
            if self.provider == "google":
                declined = any(
                    a.get("self") and a.get("responseStatus") == "declined" for a in item.get("attendees", [])
                )
                body = str(item.get("description", ""))
                busy = item.get("transparency") != "transparent" and not declined
            else:
                body = str((item.get("body") or {}).get("content", ""))
                busy = item.get("showAs") not in ("free", "workingElsewhere") and (
                    (item.get("responseStatus") or {}).get("response") != "declined"
                )
            body = body.replace("\r\n", "\n")
            metadata: dict[str, Any] = {}
            if MARKER in body:
                try:
                    data = json.loads(body.split(MARKER, 1)[1])
                    if isinstance(data, dict) and data.get("app") == "underway":
                        metadata = data
                    else:
                        pass
                except (ValueError, TypeError):
                    # An unrecognizable event belongs to the user, never to the reconciler.
                    pass
            else:
                pass
            result.append(
                RemoteEvent(
                    id=str(item["id"]),
                    title=str(item.get("summary" if self.provider == "google" else "subject", "")),
                    start=event_datetime(item["start"], timezone),
                    end=event_datetime(item["end"], timezone),
                    busy=busy,
                    etag=item.get("etag") or item.get("@odata.etag"),
                    metadata=metadata,
                )
            )
        return result

    async def put_event(
        self,
        calendar_id: str,
        key: str,
        kind: Literal["schedule", "activity"],
        title: str,
        start: datetime,
        end: datetime,
        data: dict[str, Any],
        existing_id: str | None = None,
        all_day: date | None = None,
        etag: str | None = None,
    ) -> str:
        metadata = {
            "app": "underway",
            "version": 1,
            "kind": kind,
            "key": key,
            "data": data,
            "fingerprint": fingerprint(title, start, end),
        }
        description = str(data.get("reason") or data.get("note") or "Reported activity") + MARKER + json.dumps(metadata)
        token = hashlib.sha256(f"{calendar_id}:{kind}:{key}".encode()).hexdigest()
        path = self.events_path(calendar_id)
        if self.provider == "google":
            body: dict[str, Any] = {
                "summary": title,
                "description": description,
                "start": {"dateTime": start.astimezone(UTC).isoformat()},
                "end": {"dateTime": end.astimezone(UTC).isoformat()},
                "transparency": "transparent" if kind == "activity" else "opaque",
                "reminders": {"useDefault": kind == "schedule"},
                "extendedProperties": {"private": {"underwayKind": kind, "underwayKey": key}},
            }
            if all_day:
                body.update(
                    start={"date": all_day.isoformat()}, end={"date": (all_day + timedelta(days=1)).isoformat()}
                )
            else:
                pass
            if existing_id is None:
                body["id"] = token
            else:
                pass
        else:
            body = {
                "subject": title,
                "body": {"contentType": "text", "content": description},
                "start": {"dateTime": start.astimezone(UTC).replace(tzinfo=None).isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end.astimezone(UTC).replace(tzinfo=None).isoformat(), "timeZone": "UTC"},
                "showAs": "free" if kind == "activity" else "tentative",
                "isReminderOn": kind == "schedule",
                "reminderMinutesBeforeStart": 10,
            }
            if all_day:
                # Preserve the reported local date in calendar clients.
                body.update(
                    isAllDay=True,
                    start={"dateTime": f"{all_day.isoformat()}T00:00:00", "timeZone": str(start.tzinfo)},
                    end={
                        "dateTime": f"{(all_day + timedelta(days=1)).isoformat()}T00:00:00",
                        "timeZone": str(start.tzinfo),
                    },
                )
            else:
                pass
            if existing_id is None:
                body["transactionId"] = str(uuid5(NAMESPACE_URL, token))
            else:
                pass
        if existing_id is not None:
            await self.request("PATCH", path + "/" + quote(existing_id, safe=""), body, etag=etag)
            return existing_id
        else:
            try:
                created = await self.request("POST", path, body)
            except httpx.HTTPStatusError as exc:
                if self.provider == "google" and exc.response.status_code == 409:
                    # A timed-out create may already have succeeded. Never overwrite a
                    # report correction or a manual edit while recovering that retry.
                    existing = await self.request("GET", path + "/" + token)
                    private = (existing.get("extendedProperties") or {}).get("private", {})
                    if private.get("underwayKey") != key or private.get("underwayKind") != kind:
                        raise ValueError("Calendar event identity collision.") from exc
                    elif all(
                        existing.get(field) == body.get(field) for field in ("summary", "description", "start", "end")
                    ):
                        return token
                    else:
                        raise ValueError(
                            "Calendar event already exists with different data; refresh before retrying."
                        ) from exc
                else:
                    raise
            return str(created["id"])

    async def delete_event(self, calendar_id: str, event_id: str, etag: str | None = None) -> None:
        try:
            await self.request("DELETE", self.events_path(calendar_id) + "/" + quote(event_id, safe=""), etag=etag)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (404, 410):
                pass
            else:
                raise


async def connect_calendar(
    session: AsyncSession, user_id: UUID, provider: Literal["google", "o365"], account: str
) -> SchedulingCalendar:
    if provider == "google":
        credentials = await GoogleCalendarProvider()._get_credentials(session, user_id, account)
        token = credentials.token if credentials else None
    else:
        token = await O365CalendarProvider()._get_token(session, user_id, account)
    if not token:
        raise ValueError(f"Calendar account {account} needs authentication.")
    else:
        return SchedulingCalendar(provider, token)
