"""Calendar provider abstraction for Chronos agent.

Provides a pluggable calendar interface with a stub implementation for
development/testing and stubs for Google/Outlook that can be filled in later.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CalendarEvent(BaseModel):
    """A calendar event."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    title: str
    start: datetime
    end: datetime
    description: str = ""
    location: str = ""
    all_day: bool = False


class CalendarProvider(ABC):
    """Abstract calendar interface."""

    @abstractmethod
    async def get_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        """Retrieve events in a time range."""
        ...

    @abstractmethod
    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        """Create a new calendar event."""
        ...

    @abstractmethod
    async def delete_event(self, event_id: str) -> bool:
        """Delete an event by ID."""
        ...


class StubCalendarProvider(CalendarProvider):
    """In-memory calendar for development and testing."""

    def __init__(self) -> None:
        self._events: list[CalendarEvent] = []

    async def get_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        return [e for e in self._events if e.start >= start and e.end <= end]

    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        self._events.append(event)
        return event

    async def delete_event(self, event_id: str) -> bool:
        before = len(self._events)
        self._events = [e for e in self._events if e.id != event_id]
        return len(self._events) < before


class GoogleCalendarProvider(CalendarProvider):
    """Google Calendar provider stub (requires [calendar] extra)."""

    async def get_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        raise NotImplementedError("Google Calendar integration not yet implemented")

    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        raise NotImplementedError("Google Calendar integration not yet implemented")

    async def delete_event(self, event_id: str) -> bool:
        raise NotImplementedError("Google Calendar integration not yet implemented")


class OutlookCalendarProvider(CalendarProvider):
    """Outlook Calendar provider stub (requires [calendar] extra)."""

    async def get_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        raise NotImplementedError("Outlook Calendar integration not yet implemented")

    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        raise NotImplementedError("Outlook Calendar integration not yet implemented")

    async def delete_event(self, event_id: str) -> bool:
        raise NotImplementedError("Outlook Calendar integration not yet implemented")


def get_calendar_provider(provider_name: str = "stub") -> CalendarProvider:
    """Factory for calendar providers.

    Parameters
    ----------
    provider_name : str
        One of "stub", "google", "outlook".

    Returns
    -------
    CalendarProvider
        The configured calendar provider instance.
    """
    providers = {
        "stub": StubCalendarProvider,
        "google": GoogleCalendarProvider,
        "outlook": OutlookCalendarProvider,
    }
    cls = providers.get(provider_name)
    if cls is None:
        logger.warning(
            "Unknown calendar provider '%s', falling back to stub", provider_name
        )
        cls = StubCalendarProvider
    return cls()
