"""Scheduler settings. Pure: parses an already-loaded dict, never reads files."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any

Span = tuple[time, time]


@dataclass(frozen=True)
class TaskHint:
    minutes: int | None = None
    days: frozenset[int] | None = None
    earliest: time | None = None
    covered_by: tuple[str, ...] = ()


@dataclass(frozen=True)
class SchedulerConfig:
    areas: dict[str, tuple[str, float]]  # project id -> (area name, target share)
    weekday_windows: tuple[Span, ...]
    cooking_windows: tuple[Span, ...]
    weekend_windows: tuple[Span, ...]
    default_area: str = "Inbox"
    cooking_weekdays: frozenset[int] = frozenset()
    public_holidays: frozenset[date] = frozenset()
    min_score: int = 35
    max_boost: int = 15
    same_day_score: int = 75
    default_minutes: int = 60
    max_weekday_minutes: int = 150
    max_weekend_minutes: int = 300
    skip_labels: frozenset[str] = frozenset({"waiting"})
    timezone: str = "UTC"
    task_url: str = "https://app.todoist.com/app/task/{id}"
    hints: dict[str, TaskHint] = field(default_factory=dict)


def _time(v: str) -> time:
    h, m = v.split(":")
    return time(int(h), int(m))


def _spans(raw: list[list[str]]) -> tuple[Span, ...]:
    return tuple((_time(a), _time(b)) for a, b in raw)


def _hint(raw: dict[str, Any]) -> TaskHint:
    days = raw.get("days")
    start = raw.get("start")
    return TaskHint(
        minutes=int(raw["minutes"]) if "minutes" in raw else None,
        days=frozenset(int(d) for d in days) if days is not None else None,
        earliest=_time(str(start)) if start is not None else None,
        covered_by=tuple(str(k).lower() for k in raw.get("covered_by", [])),
    )


def config_from_dict(cfg: dict[str, Any]) -> SchedulerConfig:
    w = cfg["windows"]
    return SchedulerConfig(
        areas={str(k): (str(v["name"]), float(v["target"])) for k, v in cfg["areas"].items()},
        weekday_windows=_spans(w["weekday"]),
        cooking_windows=_spans(w["cooking"]),
        weekend_windows=_spans(w["weekend"]),
        default_area=str(cfg.get("default_area", "Inbox")),
        cooking_weekdays=frozenset(int(d) for d in cfg.get("cooking_weekdays", [])),
        public_holidays=frozenset(date.fromisoformat(d) for d in cfg.get("public_holidays", [])),
        min_score=int(cfg.get("min_score", 35)),
        max_boost=int(cfg.get("max_boost", 15)),
        same_day_score=int(cfg.get("same_day_score", 75)),
        default_minutes=int(cfg.get("default_minutes", 60)),
        max_weekday_minutes=int(cfg.get("max_weekday_minutes", 150)),
        max_weekend_minutes=int(cfg.get("max_weekend_minutes", 300)),
        skip_labels=frozenset(str(x) for x in cfg.get("skip_labels", ["waiting"])),
        timezone=str(cfg.get("timezone", "UTC")),
        task_url=str(cfg.get("task_url", "https://app.todoist.com/app/task/{id}")),
        hints={str(k): _hint(v) for k, v in cfg.get("hints", {}).items()},
    )
