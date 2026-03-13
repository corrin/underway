"""Factory for calendar provider instances."""

from __future__ import annotations

import logging

from underway.providers.calendar.base import CalendarProvider
from underway.providers.calendar.google import GoogleCalendarProvider
from underway.providers.calendar.o365 import O365CalendarProvider

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, type[CalendarProvider]] = {
    "google": GoogleCalendarProvider,
    "o365": O365CalendarProvider,
}


def get_calendar_provider(provider_name: str) -> CalendarProvider | None:
    """Return a CalendarProvider instance for the given provider name, or None."""
    cls = _PROVIDERS.get(provider_name)
    if cls is None:
        logger.error("Unknown calendar provider: %s", provider_name)
        return None
    return cls()
