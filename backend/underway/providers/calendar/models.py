"""Pydantic models for calendar events (external API data, not DB models)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class CalendarEvent(BaseModel):
    """A calendar event returned from an external provider."""

    id: str
    title: str
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None
    provider: str


class CalendarEventCreate(BaseModel):
    """Data required to create a new calendar event."""

    title: str
    start: datetime
    end: datetime
    location: str | None = None
    description: str | None = None
