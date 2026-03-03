"""Tests for reactive Chronos agent (WP4)."""

import pytest
from unittest.mock import AsyncMock, patch

from packages.core.agents.chronos import ChronosAgent
from packages.core.events import Event, EventBus, Topics


@pytest.fixture
def chronos():
    return ChronosAgent()


@pytest.fixture
def bus():
    return EventBus()


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
