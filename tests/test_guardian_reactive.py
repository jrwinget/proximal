"""Tests for reactive Guardian agent (WP3)."""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from packages.core.agents.guardian import GuardianAgent
from packages.core.events import Event, EventBus, Topics
from packages.core.models import EscalationLevel


@pytest.fixture
def guardian():
    return GuardianAgent()


@pytest.fixture
def bus():
    return EventBus()


class TestGuardianBackwardCompat:
    def test_add_nudges(self, guardian):
        tasks = [{"title": f"Task {i}"} for i in range(5)]
        result = guardian.add_nudges(tasks)
        # should have nudges inserted
        assert len(result) > len(tasks)

    def test_repr(self, guardian):
        assert repr(guardian) == "GuardianAgent()"


class TestGuardianSubscriptions:
    def test_register_subscriptions(self, guardian, bus):
        guardian.register_subscriptions(bus)
        assert Topics.SESSION_STARTED in bus._handlers
        assert Topics.SESSION_TASK_COMPLETED in bus._handlers
        assert Topics.SESSION_ENDED in bus._handlers


class TestGuardianEventHandlers:
    @patch(
        "packages.core.agents.guardian.GuardianAgent._store_observation",
        new_callable=AsyncMock,
    )
    async def test_on_session_started(self, mock_store, guardian):
        event = Event(
            topic=Topics.SESSION_STARTED,
            source="session",
            session_id="s1",
            data={"goal": "test goal", "user_id": "u1"},
        )
        await guardian._on_session_started(event)
        assert "s1" in guardian._active_sessions
        mock_store.assert_called()

    @patch(
        "packages.core.agents.guardian.GuardianAgent._store_observation",
        new_callable=AsyncMock,
    )
    async def test_on_task_completed(self, mock_store, guardian):
        event = Event(
            topic=Topics.SESSION_TASK_COMPLETED,
            source="orchestrator",
            session_id="s1",
            data={"task_title": "My task"},
        )
        await guardian._on_task_completed(event)
        mock_store.assert_called_once()

    @patch(
        "packages.core.agents.guardian.GuardianAgent._store_observation",
        new_callable=AsyncMock,
    )
    async def test_on_session_ended(self, mock_store, guardian):
        guardian._active_sessions["s1"] = datetime.now(timezone.utc)
        event = Event(
            topic=Topics.SESSION_ENDED,
            source="session",
            session_id="s1",
            data={},
        )
        await guardian._on_session_ended(event)
        assert "s1" not in guardian._active_sessions
        mock_store.assert_called()

    @patch(
        "packages.core.agents.guardian.GuardianAgent._store_observation",
        new_callable=AsyncMock,
    )
    async def test_late_session_detected(self, mock_store, guardian):
        late_time = datetime(2025, 1, 1, 23, 0, 0, tzinfo=timezone.utc)
        event = Event(
            topic=Topics.SESSION_STARTED,
            source="session",
            session_id="s1",
            data={"user_id": "u1"},
            timestamp=late_time,
        )
        await guardian._on_session_started(event)
        # should have stored both session_start and late_session observations
        assert mock_store.call_count == 2


class TestGuardianEscalation:
    def test_gentle_nudge(self, guardian):
        msg = guardian.build_escalation_message(EscalationLevel.gentle_nudge)
        assert "gentle reminder" in msg.lower()

    def test_firm_reminder(self, guardian):
        msg = guardian.build_escalation_message(EscalationLevel.firm_reminder)
        assert "break" in msg.lower()

    def test_escalated_warning(self, guardian):
        msg = guardian.build_escalation_message(EscalationLevel.escalated_warning)
        assert "burnout" in msg.lower()

    def test_session_end_suggestion(self, guardian):
        msg = guardian.build_escalation_message(EscalationLevel.session_end_suggestion)
        assert "wrapping up" in msg.lower() or "rest" in msg.lower()


class TestGuardianIntegration:
    @patch(
        "packages.core.agents.guardian.GuardianAgent._store_observation",
        new_callable=AsyncMock,
    )
    async def test_full_session_flow(self, mock_store, guardian, bus):
        """Test a complete session lifecycle through the event bus."""
        guardian.register_subscriptions(bus)

        # session started
        await bus.publish(
            Event(
                topic=Topics.SESSION_STARTED,
                source="session",
                session_id="s1",
                data={"goal": "test"},
            )
        )
        assert "s1" in guardian._active_sessions

        # task completed
        await bus.publish(
            Event(
                topic=Topics.SESSION_TASK_COMPLETED,
                source="orchestrator",
                session_id="s1",
                data={"task_title": "task 1"},
            )
        )

        # session ended
        await bus.publish(
            Event(
                topic=Topics.SESSION_ENDED,
                source="session",
                session_id="s1",
                data={},
            )
        )
        assert "s1" not in guardian._active_sessions
        # 3 events (start, task, end) => at least 3 store calls
        assert mock_store.call_count >= 3
