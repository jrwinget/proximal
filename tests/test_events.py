"""Tests for the event bus foundation (WP1)."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from packages.core.events import (
    Event,
    EventBus,
    Topics,
    get_event_bus,
    reset_event_bus,
)


@pytest.fixture(autouse=True)
def _clean_singleton():
    """Reset the global singleton before each test."""
    reset_event_bus()
    yield
    reset_event_bus()


# ---------------------------------------------------------------------------
# Event model
# ---------------------------------------------------------------------------


class TestEventModel:
    def test_event_defaults(self):
        e = Event(topic="plan.created", source="planner")
        assert len(e.id) == 8
        assert e.topic == "plan.created"
        assert e.source == "planner"
        assert e.data == {}
        assert e.session_id is None
        assert e.timestamp is not None

    def test_event_with_data(self):
        e = Event(topic="plan.created", source="planner", data={"goal": "test"})
        assert e.data["goal"] == "test"

    def test_event_with_session(self):
        e = Event(topic="session.started", source="session", session_id="abc123")
        assert e.session_id == "abc123"


# ---------------------------------------------------------------------------
# Subscribe / publish
# ---------------------------------------------------------------------------


class TestPubSub:
    async def test_basic_subscribe_publish(self):
        bus = EventBus()
        handler = AsyncMock()
        bus.subscribe("plan.created", handler)

        event = Event(topic="plan.created", source="test")
        await bus.publish(event)

        handler.assert_called_once_with(event)

    async def test_multiple_handlers(self):
        bus = EventBus()
        h1 = AsyncMock()
        h2 = AsyncMock()
        bus.subscribe("plan.created", h1)
        bus.subscribe("plan.created", h2)

        event = Event(topic="plan.created", source="test")
        await bus.publish(event)

        h1.assert_called_once_with(event)
        h2.assert_called_once_with(event)

    async def test_no_subscribers(self):
        """Publishing to a topic with no subscribers should not raise."""
        bus = EventBus()
        event = Event(topic="plan.created", source="test")
        await bus.publish(event)

    async def test_unsubscribe(self):
        bus = EventBus()
        handler = AsyncMock()
        bus.subscribe("plan.created", handler)
        bus.unsubscribe("plan.created", handler)

        event = Event(topic="plan.created", source="test")
        await bus.publish(event)

        handler.assert_not_called()

    async def test_unsubscribe_nonexistent(self):
        """Unsubscribing a handler that was never subscribed should not raise."""
        bus = EventBus()
        handler = AsyncMock()
        bus.unsubscribe("plan.created", handler)


# ---------------------------------------------------------------------------
# Wildcard matching
# ---------------------------------------------------------------------------


class TestWildcards:
    async def test_wildcard_star(self):
        bus = EventBus()
        handler = AsyncMock()
        bus.subscribe("plan.*", handler)

        e1 = Event(topic="plan.created", source="test")
        e2 = Event(topic="plan.completed", source="test")
        e3 = Event(topic="session.started", source="test")

        await bus.publish(e1)
        await bus.publish(e2)
        await bus.publish(e3)

        assert handler.call_count == 2

    async def test_wildcard_all(self):
        bus = EventBus()
        handler = AsyncMock()
        bus.subscribe("*", handler)

        e1 = Event(topic="plan.created", source="test")
        e2 = Event(topic="session.started", source="test")

        await bus.publish(e1)
        await bus.publish(e2)

        assert handler.call_count == 2

    async def test_exact_match(self):
        bus = EventBus()
        handler = AsyncMock()
        bus.subscribe("plan.created", handler)

        await bus.publish(Event(topic="plan.created", source="test"))
        await bus.publish(Event(topic="plan.completed", source="test"))

        assert handler.call_count == 1


# ---------------------------------------------------------------------------
# Handler errors (graceful degradation)
# ---------------------------------------------------------------------------


class TestHandlerErrors:
    async def test_handler_exception_does_not_crash(self):
        bus = EventBus()
        bad_handler = AsyncMock(side_effect=RuntimeError("boom"))
        good_handler = AsyncMock()

        bus.subscribe("plan.created", bad_handler)
        bus.subscribe("plan.created", good_handler)

        event = Event(topic="plan.created", source="test")
        await bus.publish(event)

        bad_handler.assert_called_once()
        good_handler.assert_called_once()

    async def test_handler_exception_logged(self, caplog):
        bus = EventBus()
        bad_handler = AsyncMock(side_effect=ValueError("oops"))
        bus.subscribe("plan.created", bad_handler)

        with caplog.at_level("ERROR"):
            await bus.publish(Event(topic="plan.created", source="test"))

        assert "failed for topic plan.created" in caplog.text


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------


class TestHistory:
    async def test_history_records_events(self):
        bus = EventBus()
        e1 = Event(topic="a", source="test")
        e2 = Event(topic="b", source="test")

        await bus.publish(e1)
        await bus.publish(e2)

        assert len(bus.history) == 2
        assert bus.history[0] is e1
        assert bus.history[1] is e2

    async def test_history_capped_at_max(self):
        bus = EventBus()

        for i in range(1100):
            await bus.publish(Event(topic=f"t.{i}", source="test"))

        assert len(bus.history) == 1000

    def test_clear_history(self):
        bus = EventBus()
        bus._history.append(Event(topic="a", source="test"))
        bus.clear_history()
        assert len(bus.history) == 0


# ---------------------------------------------------------------------------
# Lifecycle (start/stop)
# ---------------------------------------------------------------------------


class TestLifecycle:
    async def test_start_stop(self):
        bus = EventBus()
        assert not bus.running

        bus.start()
        assert bus.running

        await bus.stop()
        assert not bus.running

    async def test_start_idempotent(self):
        bus = EventBus()
        bus.start()
        bus.start()  # should not raise
        assert bus.running
        await bus.stop()

    async def test_stop_idempotent(self):
        bus = EventBus()
        await bus.stop()  # should not raise
        assert not bus.running

    async def test_background_dispatch(self):
        bus = EventBus()
        handler = AsyncMock()
        bus.subscribe("plan.created", handler)

        bus.start()
        await bus.publish(Event(topic="plan.created", source="test"))
        # give the background loop time to process
        await asyncio.sleep(0.1)
        await bus.stop()

        handler.assert_called_once()

    async def test_drain_on_stop(self):
        bus = EventBus()
        handler = AsyncMock()
        bus.subscribe("plan.created", handler)

        bus.start()
        # publish several events
        for _ in range(5):
            await bus.publish(Event(topic="plan.created", source="test"))
        await asyncio.sleep(0.2)
        await bus.stop()

        assert handler.call_count == 5


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


class TestSingleton:
    def test_get_event_bus_returns_same_instance(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_reset_clears_singleton(self):
        bus1 = get_event_bus()
        reset_event_bus()
        bus2 = get_event_bus()
        assert bus1 is not bus2


# ---------------------------------------------------------------------------
# Topics constants
# ---------------------------------------------------------------------------


class TestTopics:
    def test_standard_topics_are_strings(self):
        assert isinstance(Topics.PLAN_CREATED, str)
        assert Topics.PLAN_CREATED == "plan.created"
        assert Topics.SESSION_STARTED == "session.started"
        assert Topics.GUARDIAN_NUDGE == "guardian.nudge"
        assert Topics.CHRONOS_CONFLICT == "chronos.conflict"
