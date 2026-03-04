"""Tests for calendar provider abstraction (WP4)."""

from datetime import datetime, timezone

import pytest

from packages.core.integrations.calendar_provider import (
    CalendarEvent,
    GoogleCalendarProvider,
    OutlookCalendarProvider,
    StubCalendarProvider,
    get_calendar_provider,
)


@pytest.fixture
def stub():
    return StubCalendarProvider()


class TestCalendarEvent:
    def test_defaults(self):
        e = CalendarEvent(
            title="Meeting",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        assert len(e.id) == 8
        assert e.title == "Meeting"
        assert e.all_day is False


class TestStubProvider:
    async def test_create_and_get(self, stub):
        event = CalendarEvent(
            title="Test",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        await stub.create_event(event)
        events = await stub.get_events(
            datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 2, 0, 0, tzinfo=timezone.utc),
        )
        assert len(events) == 1
        assert events[0].title == "Test"

    async def test_delete(self, stub):
        event = CalendarEvent(
            title="Delete Me",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        await stub.create_event(event)
        assert await stub.delete_event(event.id) is True
        events = await stub.get_events(
            datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 2, 0, 0, tzinfo=timezone.utc),
        )
        assert len(events) == 0

    async def test_delete_nonexistent(self, stub):
        assert await stub.delete_event("nope") is False

    async def test_filter_by_range(self, stub):
        e1 = CalendarEvent(
            title="In range",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        e2 = CalendarEvent(
            title="Out of range",
            start=datetime(2025, 1, 2, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
        )
        await stub.create_event(e1)
        await stub.create_event(e2)

        events = await stub.get_events(
            datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 23, 59, tzinfo=timezone.utc),
        )
        assert len(events) == 1
        assert events[0].title == "In range"


class TestProviderStubs:
    async def test_google_not_implemented(self):
        p = GoogleCalendarProvider()
        with pytest.raises(NotImplementedError):
            await p.get_events(datetime.now(), datetime.now())

    async def test_outlook_not_implemented(self):
        p = OutlookCalendarProvider()
        with pytest.raises(NotImplementedError):
            await p.get_events(datetime.now(), datetime.now())


class TestFactory:
    def test_stub_provider(self):
        p = get_calendar_provider("stub")
        assert isinstance(p, StubCalendarProvider)

    def test_unknown_falls_back(self):
        p = get_calendar_provider("unknown")
        assert isinstance(p, StubCalendarProvider)

    def test_google_provider(self):
        p = get_calendar_provider("google")
        assert isinstance(p, GoogleCalendarProvider)


class TestLegacyCalendarRemoved:
    """Ensure the legacy calendar.py placeholder is gone."""

    def test_legacy_calendar_module_does_not_exist(self):
        # the old placeholder file should not be on disk
        from pathlib import Path

        legacy = Path(__file__).resolve().parent.parent / "packages" / "core" / "integrations" / "calendar.py"
        assert not legacy.exists(), "legacy calendar.py should be removed"

    def test_calendar_provider_is_canonical(self):
        # calendar_provider module should be importable as the canonical calendar integration
        from packages.core.integrations.calendar_provider import CalendarProvider, get_calendar_provider

        assert CalendarProvider is not None
        assert callable(get_calendar_provider)
