"""Tests for calendar provider factory and base class."""

from underway.providers.calendar.base import CalendarProvider
from underway.providers.calendar.factory import get_calendar_provider
from underway.providers.calendar.google import GoogleCalendarProvider
from underway.providers.calendar.o365 import O365CalendarProvider


class TestCalendarProviderFactory:
    def test_get_google_provider(self) -> None:
        provider = get_calendar_provider("google")
        assert provider is not None
        assert isinstance(provider, GoogleCalendarProvider)
        assert isinstance(provider, CalendarProvider)

    def test_get_o365_provider(self) -> None:
        provider = get_calendar_provider("o365")
        assert provider is not None
        assert isinstance(provider, O365CalendarProvider)
        assert isinstance(provider, CalendarProvider)

    def test_unknown_provider_returns_none(self) -> None:
        provider = get_calendar_provider("unknown")
        assert provider is None

    def test_empty_provider_returns_none(self) -> None:
        provider = get_calendar_provider("")
        assert provider is None
