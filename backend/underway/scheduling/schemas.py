"""Validated, provider-independent inputs and outputs for the weekly planner."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from typing import Literal, Self
from uuid import uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceRef(Schema):
    provider: Literal["todoist", "google_tasks", "outlook"]
    account: str = Field(min_length=1)
    container_id: str = Field(min_length=1)
    task_id: str | None = None

    @property
    def key(self) -> str:
        identity = ["task", self.task_id] if self.task_id else ["container", self.container_id]
        return json.dumps([self.provider, self.account, *identity], separators=(",", ":"))


class Window(Schema):
    weekdays: list[int] = Field(min_length=1)
    start: time
    end: time

    @model_validator(mode="after")
    def validate_window(self) -> Self:
        if self.end <= self.start or any(day not in range(7) for day in self.weekdays):
            raise ValueError("Windows use weekdays 0-6 and must end after they start; split overnight windows.")
        else:
            return self


class IntentionNode(Schema):
    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    parent_id: str | None = None
    title: str = Field(min_length=1)
    instructions: str = ""
    weekly_minutes: int | None = Field(default=None, gt=0)
    interval_days: int | None = Field(default=None, gt=0)
    repeatable: bool = True
    preferred_windows: list[Window] = Field(default_factory=list)
    sources: list[SourceRef] = Field(default_factory=list)
    deadline: AwareDatetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)


class Intentions(Schema):
    version: Literal[1] = 1
    revision: int = Field(default=0, ge=0)
    enabled: bool = False
    timezone: str = "Pacific/Auckland"
    slot_minutes: Literal[30, 60, 120] = 60
    allowed_windows: list[Window] = Field(default_factory=list)
    calendar_provider: Literal["google", "o365"] | None = None
    calendar_account: str | None = None
    schedule_calendar_id: str | None = None
    activity_calendar_id: str | None = None
    nodes: list[IntentionNode] = Field(default_factory=list)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Choose a valid IANA timezone.") from exc
        return value

    @model_validator(mode="after")
    def validate_tree(self) -> Self:
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError("Node IDs must be unique.")
        else:
            pass
        bindings: set[str] = set()
        for node in self.nodes:
            seen = {node.id}
            parent = node.parent_id
            while parent is not None:
                if parent not in nodes or parent in seen:
                    raise ValueError("Every parent must exist and the activity tree must be acyclic.")
                else:
                    seen.add(parent)
                    parent = nodes[parent].parent_id
            for source in node.sources:
                if source.key in bindings:
                    raise ValueError("A source binding can belong to only one intention node.")
                else:
                    bindings.add(source.key)
        if self.enabled and not (
            self.nodes and self.allowed_windows and self.calendar_provider and self.calendar_account
        ):
            raise ValueError("Configure activities, allowed hours, and a calendar account before enabling scheduling.")
        else:
            pass
        if self.schedule_calendar_id and self.schedule_calendar_id == self.activity_calendar_id:
            raise ValueError("Suggestions and reported activity must use different calendars.")
        else:
            return self


class SourceActivity(Schema):
    source: SourceRef
    title: str
    description: str = ""
    parent_task_id: str | None = None
    priority: int = 2
    due: datetime | None = None
    deadline: AwareDatetime | None = None
    estimated_minutes: int | None = Field(default=None, gt=0)


class ActivityReport(Schema):
    id: str = Field(default_factory=lambda: str(uuid4()), min_length=1, max_length=100)
    node_id: str = Field(min_length=1)
    date: date
    minutes: int | None = Field(default=None, gt=0, le=1440)
    source: SourceRef | None = None
    fulfilled_intentions: list[str] = Field(default_factory=list)
    note: str = ""


class CalendarBlock(Schema):
    id: str
    start: AwareDatetime
    end: AwareDatetime
    title: str = ""
    node_id: str | None = None
    source: SourceRef | None = None
    fulfilled_intentions: list[str] = Field(default_factory=list)
    protected: bool = False
    reason: str = ""

    @model_validator(mode="after")
    def valid_interval(self) -> Self:
        if self.end <= self.start:
            raise ValueError("Calendar blocks must have positive duration.")
        else:
            return self


class Snapshot(Schema):
    intentions: Intentions
    activities: list[SourceActivity] = Field(default_factory=list)
    reports: list[ActivityReport] = Field(default_factory=list)
    busy: list[CalendarBlock] = Field(default_factory=list)
    preserved: list[CalendarBlock] = Field(default_factory=list)


class WeeklyPlan(Schema):
    blocks: list[CalendarBlock] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class NodeProgress(Schema):
    node_id: str
    minutes: int
    percentage_of_recorded_time: float
    target_percentage: float | None
