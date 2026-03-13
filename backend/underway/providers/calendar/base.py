"""Abstract base class for calendar providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from underway.providers.calendar.models import CalendarEvent, CalendarEventCreate


class CalendarProvider(ABC):
    """Base class for calendar providers (Google, O365)."""

    @abstractmethod
    async def get_events(
        self,
        session: AsyncSession,
        user_id: UUID,
        email: str,
        start: datetime,
        end: datetime,
    ) -> list[CalendarEvent]:
        """Retrieve calendar events for the given time range."""

    @abstractmethod
    async def create_event(
        self,
        session: AsyncSession,
        user_id: UUID,
        email: str,
        event: CalendarEventCreate,
    ) -> CalendarEvent:
        """Create a new calendar event."""

    @abstractmethod
    async def delete_event(
        self,
        session: AsyncSession,
        user_id: UUID,
        email: str,
        event_id: str,
    ) -> bool:
        """Delete a calendar event. Returns True if deleted."""
