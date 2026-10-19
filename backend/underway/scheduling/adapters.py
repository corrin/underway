"""Pure translators between connector payloads (already fetched) and core types."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import date, datetime, time, timedelta
from typing import Any, cast

from underway.scheduling.config import SchedulerConfig
from underway.scheduling.core import Block, Busy, Task

SCORE_RE = re.compile(r"^\[(\d{2})\]\s*(.*)$")
_TASK_LINK_RE = re.compile(r"/task/(\w+)")
_SERIAL_RE = re.compile(r"\d{5}(\.0)?")
_ISO_PREFIX_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_SHEETS_EPOCH = date(1899, 12, 30)

Payload = dict[str, object] | list[object]


def unwrap(text: str) -> Payload:
    """Parse JSON that may be wrapped in connector chatter."""
    stripped = text.lstrip()
    first = text.index("[") if stripped.startswith("[") else text.index("{")
    last = max(text.rfind("}"), text.rfind("]"))
    return cast(Payload, json.loads(text[first : last + 1]))


def _rows(payload: Payload, key: str) -> list[dict[str, Any]]:
    rows = payload[key] if isinstance(payload, dict) else payload
    return cast(list[dict[str, Any]], rows)


def task_from_todoist(r: dict[str, Any], cfg: SchedulerConfig) -> Task | None:
    m = SCORE_RE.match(str(r.get("content", "")))
    if not m or r.get("checked") or cfg.skip_labels & set(r.get("labels", [])):
        return None
    else:
        pass  # scored, open and ours
    tid = str(r["id"])
    hint = cfg.hints.get(tid)
    due_raw = r.get("dueDate")
    return Task(
        id=tid,
        title=str(r["content"]),
        score=int(m.group(1)),
        area=cfg.areas.get(str(r.get("projectId")), (cfg.default_area, 0.0))[0],
        due=date.fromisoformat(str(due_raw)[:10]) if due_raw else None,
        recurrence=str(r["recurring"]) if r.get("recurring") else None,
        minutes=hint.minutes if hint and hint.minutes else cfg.default_minutes,
        days=hint.days if hint else None,
        earliest=hint.earliest if hint else None,
        covered_by=hint.covered_by if hint else (),
    )


def tasks_from_payload(payload: Payload, cfg: SchedulerConfig) -> list[Task]:
    out: list[Task] = []
    for r in _rows(payload, "tasks"):
        t = task_from_todoist(r, cfg)
        if t is not None:
            out.append(t)
        else:
            pass  # skipped
    return out


def _dt(v: dict[str, Any]) -> datetime:
    if "dateTime" in v:
        return datetime.fromisoformat(str(v["dateTime"])).replace(tzinfo=None)  # local wall time
    else:
        return datetime.combine(date.fromisoformat(str(v["date"])), time(0))


def is_pqm(e: dict[str, Any]) -> bool:
    return (e.get("description") or "").strip().splitlines()[-1:] == ["pqm"]


def busy_from_payload(payload: Payload) -> list[Busy]:
    return [
        Busy(_dt(e["start"]), _dt(e["end"]), str(e.get("summary", "")))
        for e in _rows(payload, "events")
        if e.get("status") != "cancelled" and not is_pqm(e) and e.get("transparency") != "transparent"
    ]


def pinned_from_payload(payload: Payload, day: date) -> list[Block]:
    """Existing pqm blocks on ``day``: today's plan stays as already announced."""
    out: list[Block] = []
    for e in _rows(payload, "events"):
        if e.get("status") == "cancelled" or not is_pqm(e):
            continue
        else:
            pass  # live pqm block
        s, en = _dt(e["start"]), _dt(e["end"])
        if s.date() != day:
            continue
        else:
            pass  # on the pinned day
        m = _TASK_LINK_RE.search(str(e.get("description", "")))
        tid = m.group(1) if m else str(e["id"])
        out.append(Block(tid, str(e.get("summary", "")), s, en, "kept", int((en - s).total_seconds() // 60)))
    return out


def sheet_date(v: str) -> date | None:
    v = (v or "").strip()
    if not v:
        return None
    elif _SERIAL_RE.fullmatch(v):
        return _SHEETS_EPOCH + timedelta(days=int(float(v)))
    else:
        try:
            return datetime.strptime(v, "%d %b %Y").date()
        except ValueError:
            return None


def minutes_by_area(csv_text: str, since: date, until: date) -> dict[str, float]:
    """Sum minutes per top-level area from time-log CSV rows in [since, until]."""
    out: dict[str, float] = {}
    for row in list(csv.reader(io.StringIO(csv_text)))[1:]:
        if len(row) < 6:
            continue
        else:
            pass  # full row
        d = sheet_date(row[1])
        if d is None and _ISO_PREFIX_RE.match(row[0]):
            d = date.fromisoformat(row[0][:10])  # entry id carries the date
        else:
            pass  # date column parsed, or no usable date
        if d is None or not (since <= d <= until):
            continue
        else:
            area = row[5].split(" > ")[0].strip()
            out[area] = out.get(area, 0.0) + float(row[2] or 0)
    return out


def to_event(b: Block, cfg: SchedulerConfig) -> dict[str, Any]:
    return {
        "summary": b.title,
        "description": f"{cfg.task_url.format(id=b.task_id)}\nWhy: {b.reason}.\nEstimate: {b.minutes} min\npqm",
        "startTime": b.start.isoformat(),
        "endTime": b.end.isoformat(),
        "timeZone": cfg.timezone,
        "visibility": "private",
        "overrideReminders": [{"method": "popup", "minutes": 0}],
    }
