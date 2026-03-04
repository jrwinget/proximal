"""Tests for reactive Chronos agent (WP4)."""

from datetime import datetime, timedelta, timezone

import pytest
from unittest.mock import AsyncMock, patch

from packages.core.agents.chronos import ChronosAgent
from packages.core.events import Event, EventBus, Topics
from packages.core.integrations.calendar_provider import (
    CalendarEvent,
    CalendarProvider,
    StubCalendarProvider,
)


@pytest.fixture
def chronos():
    return ChronosAgent()


@pytest.fixture
def bus():
    return EventBus()


@pytest.fixture
def stub_provider():
    return StubCalendarProvider()


@pytest.fixture
def chronos_with_provider(stub_provider):
    return ChronosAgent(calendar_provider=stub_provider)


class TestChronosBackwardCompat:
    def test_create_schedule(self, chronos):
        tasks = [{"title": f"Task {i}"} for i in range(3)]
        result = chronos.create_schedule(tasks)
        assert len(result) >= 3

    def test_repr(self, chronos):
        assert repr(chronos) == "ChronosAgent()"


class TestChronosSubscriptions:
    def test_register_subscriptions(self, chronos, bus):
        chronos.register_subscriptions(bus)
        assert "calendar.*" in bus._handlers
        assert Topics.TASK_ESTIMATE_EXCEEDED in bus._handlers
        assert Topics.PLAN_CREATED in bus._handlers


class TestChronosEventHandlers:
    async def test_on_calendar_event(self, chronos):
        event = Event(
            topic="calendar.event_created",
            source="calendar",
            data={"title": "Meeting"},
        )
        # should not raise
        await chronos._on_calendar_event(event)

    @patch("packages.core.estimate_learning.record_task_timing", new_callable=AsyncMock)
    async def test_on_estimate_exceeded(self, mock_record, chronos):
        event = Event(
            topic=Topics.TASK_ESTIMATE_EXCEEDED,
            source="orchestrator",
            session_id="s1",
            data={
                "task_title": "Build API",
                "task_category": "coding",
                "estimated_hours": 2.0,
                "actual_hours": 4.0,
                "user_id": "test",
            },
        )
        await chronos._on_estimate_exceeded(event)
        mock_record.assert_called_once()

    async def test_on_plan_created(self, chronos):
        event = Event(
            topic=Topics.PLAN_CREATED,
            source="orchestrator",
            data={"goal": "test", "task_count": 5},
        )
        # should not raise
        await chronos._on_plan_created(event)


class TestChronosIntegration:
    async def test_event_flow(self, chronos, bus):
        """Test event routing through the bus."""
        chronos.register_subscriptions(bus)

        handler_called = []

        original_handler = chronos._on_plan_created

        async def tracking_handler(event):
            handler_called.append(event.topic)
            await original_handler(event)

        # replace handler to track calls
        bus.unsubscribe(Topics.PLAN_CREATED, chronos._on_plan_created)
        bus.subscribe(Topics.PLAN_CREATED, tracking_handler)

        await bus.publish(
            Event(
                topic=Topics.PLAN_CREATED,
                source="orchestrator",
                data={"goal": "test"},
            )
        )

        assert Topics.PLAN_CREATED in handler_called


class TestChronosCalendarProvider:
    """Tests for CalendarProvider integration in ChronosAgent."""

    def test_accepts_calendar_provider(self, stub_provider):
        """ChronosAgent accepts a CalendarProvider via constructor."""
        agent = ChronosAgent(calendar_provider=stub_provider)
        assert agent._calendar_provider is stub_provider

    def test_defaults_to_stub_when_no_provider(self):
        """ChronosAgent falls back to StubCalendarProvider when none given."""
        agent = ChronosAgent()
        assert isinstance(agent._calendar_provider, StubCalendarProvider)

    async def test_on_calendar_event_checks_conflicts(
        self, chronos_with_provider, stub_provider
    ):
        """Calendar event handler queries provider for conflicts."""
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        # add an existing event that overlaps with 10:00-11:00
        existing = CalendarEvent(
            title="Team standup",
            start=now.replace(hour=10, minute=0),
            end=now.replace(hour=10, minute=30),
        )
        await stub_provider.create_event(existing)

        event = Event(
            topic="calendar.event_created",
            source="calendar",
            data={
                "title": "New meeting",
                "start": (now.replace(hour=10, minute=0)).isoformat(),
                "end": (now.replace(hour=11, minute=0)).isoformat(),
            },
        )
        result = await chronos_with_provider._on_calendar_event(event)
        # should return conflict information (not None) when conflicts exist
        assert result is not None
        assert len(result) > 0

    async def test_on_calendar_event_no_conflicts(self, chronos_with_provider):
        """Calendar event handler returns empty list when no conflicts."""
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        event = Event(
            topic="calendar.event_created",
            source="calendar",
            data={
                "title": "Solo meeting",
                "start": (now.replace(hour=10, minute=0)).isoformat(),
                "end": (now.replace(hour=11, minute=0)).isoformat(),
            },
        )
        result = await chronos_with_provider._on_calendar_event(event)
        assert result == []

    async def test_on_calendar_event_emits_conflict_event(
        self, chronos_with_provider, stub_provider, bus
    ):
        """ChronosAgent emits CHRONOS_CONFLICT event when conflicts found."""
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        existing = CalendarEvent(
            title="Existing meeting",
            start=now.replace(hour=14, minute=0),
            end=now.replace(hour=15, minute=0),
        )
        await stub_provider.create_event(existing)

        chronos_with_provider.register_subscriptions(bus)

        conflict_events = []

        async def capture_conflict(evt: Event):
            conflict_events.append(evt)

        bus.subscribe(Topics.CHRONOS_CONFLICT, capture_conflict)

        event = Event(
            topic="calendar.event_created",
            source="calendar",
            data={
                "title": "Overlapping meeting",
                "start": (now.replace(hour=14, minute=0)).isoformat(),
                "end": (now.replace(hour=14, minute=30)).isoformat(),
            },
        )
        await bus.publish(event)

        assert len(conflict_events) == 1
        assert conflict_events[0].source == "chronos"

    async def test_on_plan_created_checks_conflicts(
        self, chronos_with_provider, stub_provider
    ):
        """Plan created handler checks tasks against calendar."""
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        existing = CalendarEvent(
            title="Lunch meeting",
            start=now.replace(hour=12, minute=0),
            end=now.replace(hour=13, minute=0),
        )
        await stub_provider.create_event(existing)

        event = Event(
            topic=Topics.PLAN_CREATED,
            source="orchestrator",
            data={
                "goal": "Build feature",
                "tasks": [
                    {"title": "Design", "start": "09:00", "end": "10:00"},
                    {"title": "Implement", "start": "12:00", "end": "13:00"},
                ],
            },
        )
        result = await chronos_with_provider._on_plan_created(event)
        # should detect the 12:00-13:00 conflict with lunch meeting
        assert result is not None
        assert len(result) > 0

    async def test_on_plan_created_emits_conflict_event(
        self, chronos_with_provider, stub_provider, bus
    ):
        """Plan created handler emits CHRONOS_CONFLICT when conflicts found."""
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        existing = CalendarEvent(
            title="Doctor appointment",
            start=now.replace(hour=11, minute=0),
            end=now.replace(hour=12, minute=0),
        )
        await stub_provider.create_event(existing)

        chronos_with_provider.register_subscriptions(bus)

        conflict_events = []

        async def capture_conflict(evt: Event):
            conflict_events.append(evt)

        bus.subscribe(Topics.CHRONOS_CONFLICT, capture_conflict)

        event = Event(
            topic=Topics.PLAN_CREATED,
            source="orchestrator",
            data={
                "goal": "Build feature",
                "tasks": [
                    {"title": "Code review", "start": "11:00", "end": "12:00"},
                ],
            },
        )
        await bus.publish(event)

        assert len(conflict_events) == 1
        assert "conflicts" in conflict_events[0].data

    async def test_graceful_failure_on_provider_error(self):
        """ChronosAgent returns None when provider raises an exception."""
        failing_provider = AsyncMock(spec=CalendarProvider)
        failing_provider.get_events.side_effect = RuntimeError("connection lost")

        agent = ChronosAgent(calendar_provider=failing_provider)
        event = Event(
            topic="calendar.event_created",
            source="calendar",
            data={
                "title": "Meeting",
                "start": datetime.now(timezone.utc).isoformat(),
                "end": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            },
        )
        result = await agent._on_calendar_event(event)
        assert result is None

    async def test_graceful_failure_on_plan_created_provider_error(self):
        """ChronosAgent returns None when provider fails during plan check."""
        failing_provider = AsyncMock(spec=CalendarProvider)
        failing_provider.get_events.side_effect = RuntimeError("timeout")

        agent = ChronosAgent(calendar_provider=failing_provider)
        event = Event(
            topic=Topics.PLAN_CREATED,
            source="orchestrator",
            data={
                "goal": "Test",
                "tasks": [{"title": "Task", "start": "09:00", "end": "10:00"}],
            },
        )
        result = await agent._on_plan_created(event)
        assert result is None

    async def test_stub_provider_works_by_default(self):
        """ChronosAgent with default StubCalendarProvider operates correctly."""
        agent = ChronosAgent()
        event = Event(
            topic="calendar.event_created",
            source="calendar",
            data={
                "title": "Meeting",
                "start": datetime.now(timezone.utc).isoformat(),
                "end": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            },
        )
        # stub has no events, so no conflicts
        result = await agent._on_calendar_event(event)
        assert result == []
