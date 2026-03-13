"""Tests for calendar Pydantic models."""

from datetime import UTC, datetime

from underway.providers.calendar.models import CalendarEvent, CalendarEventCreate


class TestCalendarEvent:
    def test_basic_event(self) -> None:
        event = CalendarEvent(
            id="evt-1",
            title="Team standup",
            start=datetime(2026, 3, 11, 9, 0, tzinfo=UTC),
            end=datetime(2026, 3, 11, 9, 30, tzinfo=UTC),
            provider="google",
        )
        assert event.id == "evt-1"
        assert event.title == "Team standup"
        assert event.location is None
        assert event.description is None
        assert event.provider == "google"

    def test_event_with_optional_fields(self) -> None:
        event = CalendarEvent(
            id="evt-2",
            title="Lunch",
            start=datetime(2026, 3, 11, 12, 0, tzinfo=UTC),
            end=datetime(2026, 3, 11, 13, 0, tzinfo=UTC),
            location="Cafe",
            description="Team lunch",
            provider="o365",
        )
        assert event.location == "Cafe"
        assert event.description == "Team lunch"

    def test_event_serialization(self) -> None:
        event = CalendarEvent(
            id="evt-3",
            title="Demo",
            start=datetime(2026, 3, 11, 14, 0, tzinfo=UTC),
            end=datetime(2026, 3, 11, 15, 0, tzinfo=UTC),
            provider="google",
        )
        data = event.model_dump(mode="json")
        assert data["id"] == "evt-3"
        assert isinstance(data["start"], str)


class TestCalendarEventCreate:
    def test_basic_create(self) -> None:
        event = CalendarEventCreate(
            title="New meeting",
            start=datetime(2026, 3, 12, 10, 0, tzinfo=UTC),
            end=datetime(2026, 3, 12, 11, 0, tzinfo=UTC),
        )
        assert event.title == "New meeting"
        assert event.location is None

    def test_create_with_all_fields(self) -> None:
        event = CalendarEventCreate(
            title="Offsite",
            start=datetime(2026, 3, 12, 10, 0, tzinfo=UTC),
            end=datetime(2026, 3, 12, 17, 0, tzinfo=UTC),
            location="Conference room",
            description="Annual offsite",
        )
        assert event.location == "Conference room"
        assert event.description == "Annual offsite"
