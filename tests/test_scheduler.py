"""Tests for the workflow scheduler (cron, event, and lifecycle management)."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.core.workflows.definition import (
    TriggerType,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowTrigger,
)
from packages.core.workflows.executor import WorkflowExecutor, WorkflowExecution
from packages.core.workflows.scheduler import WorkflowScheduler, _should_run_now
from packages.core.events import Event, reset_event_bus


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_manual_workflow(name: str, max_per_day: int = 10) -> WorkflowDefinition:
    """Create a simple manual-trigger workflow for testing."""
    return WorkflowDefinition(
        name=name,
        trigger=WorkflowTrigger(trigger_type=TriggerType.manual),
        steps=[WorkflowStep(name="s1", agent="guardian", method="add_nudges")],
        max_auto_runs_per_day=max_per_day,
    )


def _make_cron_workflow(name: str, cron: str = "0 9 * * *") -> WorkflowDefinition:
    """Create a cron-triggered workflow."""
    return WorkflowDefinition(
        name=name,
        trigger=WorkflowTrigger(trigger_type=TriggerType.cron, cron_expression=cron),
        steps=[WorkflowStep(name="s1", agent="guardian", method="add_nudges")],
        max_auto_runs_per_day=10,
    )


def _make_event_workflow(name: str, topic: str) -> WorkflowDefinition:
    """Create an event-triggered workflow."""
    return WorkflowDefinition(
        name=name,
        trigger=WorkflowTrigger(trigger_type=TriggerType.event, event_topic=topic),
        steps=[WorkflowStep(name="s1", agent="guardian", method="add_nudges")],
        max_auto_runs_per_day=10,
    )


def _stub_execution(
    wf: WorkflowDefinition, status: str = "completed"
) -> WorkflowExecution:
    """Return a pre-populated WorkflowExecution stub."""
    execution = WorkflowExecution(wf)
    execution.status = status
    return execution


@pytest.fixture(autouse=True)
def _reset_bus():
    """Reset the global event bus between tests."""
    reset_event_bus()
    yield
    reset_event_bus()


# ---------------------------------------------------------------------------
# Workflow registration
# ---------------------------------------------------------------------------


class TestSchedulerRegistration:
    """Tests for registering workflows with the scheduler."""

    def test_builtins_loaded_on_init(self):
        """Scheduler should start with the four built-in workflows."""
        scheduler = WorkflowScheduler()
        assert len(scheduler.workflows) == 4
        assert "daily_planning" in scheduler.workflows

    def test_register_custom_workflow(self):
        """Registering a custom workflow should make it available."""
        scheduler = WorkflowScheduler()
        custom = _make_manual_workflow("custom_wf")
        scheduler.register(custom)
        assert "custom_wf" in scheduler.workflows
        # builtins should still be present
        assert len(scheduler.workflows) == 5

    def test_register_overwrites_same_name(self):
        """Registering with an existing name should replace the old workflow."""
        scheduler = WorkflowScheduler()
        wf1 = _make_manual_workflow("dup", max_per_day=5)
        wf2 = _make_manual_workflow("dup", max_per_day=99)
        scheduler.register(wf1)
        scheduler.register(wf2)
        assert scheduler.workflows["dup"].max_auto_runs_per_day == 99

    def test_workflows_property_returns_copy(self):
        """The workflows property should return a copy, not the internal dict."""
        scheduler = WorkflowScheduler()
        wfs = scheduler.workflows
        wfs["injected"] = _make_manual_workflow("injected")
        assert "injected" not in scheduler.workflows


# ---------------------------------------------------------------------------
# Daily run cap
# ---------------------------------------------------------------------------


class TestSchedulerDailyCap:
    """Tests for max_auto_runs_per_day enforcement."""

    @pytest.mark.asyncio
    async def test_cap_is_respected(self):
        """Once the daily cap is reached, further runs should be skipped."""
        mock_executor = MagicMock(spec=WorkflowExecutor)
        wf = _make_manual_workflow("capped", max_per_day=2)
        mock_executor.execute = AsyncMock(
            side_effect=lambda w: _stub_execution(w, "completed"),
        )

        scheduler = WorkflowScheduler(executor=mock_executor)
        scheduler.register(wf)

        # first two runs should succeed
        exec1 = await scheduler.run_once("capped")
        exec2 = await scheduler.run_once("capped")
        assert exec1.status == "completed"
        assert exec2.status == "completed"

        # third run should be skipped
        exec3 = await scheduler.run_once("capped")
        assert exec3.status == "skipped"
        assert "cap" in exec3.error.lower()

        # executor.execute should have been called exactly twice
        assert mock_executor.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_run_once_nonexistent_returns_none(self):
        """Running a workflow that does not exist should return None."""
        scheduler = WorkflowScheduler()
        result = await scheduler.run_once("does_not_exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_history_records_executions(self):
        """Each execution should be appended to scheduler history."""
        mock_executor = MagicMock(spec=WorkflowExecutor)
        wf = _make_manual_workflow("hist_wf")
        mock_executor.execute = AsyncMock(
            side_effect=lambda w: _stub_execution(w, "completed"),
        )

        scheduler = WorkflowScheduler(executor=mock_executor)
        scheduler.register(wf)

        await scheduler.run_once("hist_wf")
        await scheduler.run_once("hist_wf")

        assert len(scheduler.history) == 2
        assert all(e.status == "completed" for e in scheduler.history)


# ---------------------------------------------------------------------------
# Event-triggered workflows
# ---------------------------------------------------------------------------


class TestSchedulerEventTriggers:
    """Tests for event-triggered workflow execution."""

    @pytest.mark.asyncio
    async def test_event_fires_workflow(self):
        """Publishing a matching event should execute the workflow."""
        mock_executor = MagicMock(spec=WorkflowExecutor)
        mock_executor.execute = AsyncMock(
            side_effect=lambda w: _stub_execution(w, "completed"),
        )

        scheduler = WorkflowScheduler(executor=mock_executor)

        # remove builtins so only our test workflow is event-wired
        scheduler._workflows.clear()
        event_wf = _make_event_workflow("on_nudge", "guardian.nudge")
        scheduler.register(event_wf)

        scheduler.start()

        # the handler was wired during start() via the real get_event_bus
        # singleton, so we publish through the same bus instance
        from packages.core.events import get_event_bus

        bus = get_event_bus()
        event = Event(topic="guardian.nudge", source="test")
        await bus.publish(event)

        # the handler should have triggered an execution
        mock_executor.execute.assert_awaited_once()

        await scheduler.stop()

    @pytest.mark.asyncio
    async def test_non_matching_event_does_not_fire(self):
        """Publishing an event on a different topic should not trigger the workflow."""
        mock_executor = MagicMock(spec=WorkflowExecutor)
        mock_executor.execute = AsyncMock(
            side_effect=lambda w: _stub_execution(w, "completed"),
        )

        scheduler = WorkflowScheduler(executor=mock_executor)
        scheduler._workflows.clear()
        event_wf = _make_event_workflow("on_nudge", "guardian.nudge")
        scheduler.register(event_wf)

        scheduler.start()

        from packages.core.events import get_event_bus

        bus = get_event_bus()
        event = Event(topic="plan.created", source="test")
        await bus.publish(event)

        # no match -- should not execute
        mock_executor.execute.assert_not_awaited()

        await scheduler.stop()


# ---------------------------------------------------------------------------
# Scheduler start / stop lifecycle
# ---------------------------------------------------------------------------


class TestSchedulerLifecycle:
    """Tests for scheduler start and stop behaviour."""

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self):
        """Starting the scheduler should set the _running flag."""
        scheduler = WorkflowScheduler()
        # patch asyncio.ensure_future to prevent real tasks
        with patch(
            "packages.core.workflows.scheduler.asyncio.ensure_future"
        ) as mock_ef:
            mock_ef.return_value = MagicMock()
            scheduler.start()

        assert scheduler._running is True

    @pytest.mark.asyncio
    async def test_stop_clears_running_flag(self):
        """Stopping the scheduler should clear the _running flag and cancel tasks."""
        scheduler = WorkflowScheduler()

        # create real tasks that can be cancelled and awaited
        real_ensure_future = asyncio.ensure_future

        async def _hang_forever():
            await asyncio.sleep(3600)

        def _make_cancellable(coro):
            # discard the original coroutine (would need a running loop, etc.)
            if hasattr(coro, "close"):
                coro.close()
            return real_ensure_future(_hang_forever())

        with patch(
            "packages.core.workflows.scheduler.asyncio.ensure_future",
            side_effect=_make_cancellable,
        ):
            scheduler.start()

        await scheduler.stop()

        assert scheduler._running is False
        assert scheduler._tasks == {}

    @pytest.mark.asyncio
    async def test_double_start_is_idempotent(self):
        """Calling start() twice should not duplicate tasks."""
        scheduler = WorkflowScheduler()
        call_count = 0

        def counting_ensure_future(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            return mock

        with patch(
            "packages.core.workflows.scheduler.asyncio.ensure_future",
            side_effect=counting_ensure_future,
        ):
            scheduler.start()
            first_count = call_count
            scheduler.start()  # should be a no-op
            second_count = call_count

        assert first_count == second_count

    @pytest.mark.asyncio
    async def test_disabled_workflows_not_scheduled(self):
        """Disabled workflows should not get tasks created during start()."""
        mock_executor = MagicMock(spec=WorkflowExecutor)
        scheduler = WorkflowScheduler(executor=mock_executor)
        scheduler._workflows.clear()

        enabled_wf = _make_cron_workflow("enabled_cron")
        disabled_wf = _make_cron_workflow("disabled_cron")
        disabled_wf.enabled = False

        scheduler.register(enabled_wf)
        scheduler.register(disabled_wf)

        with patch(
            "packages.core.workflows.scheduler.asyncio.ensure_future"
        ) as mock_ef:
            mock_ef.return_value = MagicMock()
            scheduler.start()

        # only the enabled workflow should have a task
        assert "enabled_cron" in scheduler._tasks
        assert "disabled_cron" not in scheduler._tasks

        # clean up
        scheduler._running = False
        scheduler._tasks.clear()


# ---------------------------------------------------------------------------
# Cron loop — uses mocked asyncio.sleep
# ---------------------------------------------------------------------------


class TestCronLoop:
    """Tests for the cron polling loop, using mocked sleep to avoid real waits."""

    @pytest.mark.asyncio
    async def test_cron_loop_executes_when_should_run(self):
        """The cron loop should execute the workflow when _should_run_now is True."""
        mock_executor = MagicMock(spec=WorkflowExecutor)
        mock_executor.execute = AsyncMock(
            side_effect=lambda w: _stub_execution(w, "completed"),
        )
        scheduler = WorkflowScheduler(executor=mock_executor)
        scheduler._running = True

        wf = _make_cron_workflow("cron_test", cron="* * * * *")

        call_count = 0

        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            # stop after the second sleep (one before check, one after execution)
            if call_count >= 2:
                scheduler._running = False

        with (
            patch(
                "packages.core.workflows.scheduler.asyncio.sleep",
                side_effect=fake_sleep,
            ),
            patch(
                "packages.core.workflows.scheduler._should_run_now", return_value=True
            ),
        ):
            await scheduler._cron_loop(wf)

        # the executor should have been called at least once
        assert mock_executor.execute.await_count >= 1

    @pytest.mark.asyncio
    async def test_cron_loop_skips_when_should_not_run(self):
        """The cron loop should not execute when _should_run_now is False."""
        mock_executor = MagicMock(spec=WorkflowExecutor)
        mock_executor.execute = AsyncMock()
        scheduler = WorkflowScheduler(executor=mock_executor)
        scheduler._running = True

        wf = _make_cron_workflow("cron_skip")

        call_count = 0

        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                scheduler._running = False

        with (
            patch(
                "packages.core.workflows.scheduler.asyncio.sleep",
                side_effect=fake_sleep,
            ),
            patch(
                "packages.core.workflows.scheduler._should_run_now", return_value=False
            ),
        ):
            await scheduler._cron_loop(wf)

        mock_executor.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_cron_loop_handles_cancellation(self):
        """The cron loop should exit cleanly on CancelledError."""
        scheduler = WorkflowScheduler()
        scheduler._running = True
        wf = _make_cron_workflow("cancel_test")

        async def fake_sleep(seconds):
            raise asyncio.CancelledError

        with patch(
            "packages.core.workflows.scheduler.asyncio.sleep", side_effect=fake_sleep
        ):
            # should not raise
            await scheduler._cron_loop(wf)


# ---------------------------------------------------------------------------
# _should_run_now helper
# ---------------------------------------------------------------------------


class TestShouldRunNow:
    """Tests for the simplified cron matching helper."""

    def test_wildcard_matches(self):
        """A fully-wildcarded expression should always match."""
        assert _should_run_now("* * * * *") is True

    def test_invalid_format_returns_false(self):
        """Expressions with wrong number of parts should return False."""
        assert _should_run_now("") is False
        assert _should_run_now("* *") is False
        assert _should_run_now("0 9 * * * extra") is False

    def test_specific_minute_mismatch(self):
        """A specific minute that does not match now should return False."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        wrong_minute = (now.minute + 1) % 60
        assert _should_run_now(f"{wrong_minute} * * * *") is False

    def test_specific_minute_match(self):
        """A specific minute that matches now should return True."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        assert _should_run_now(f"{now.minute} * * * *") is True

    def test_dow_range(self):
        """Day-of-week ranges should be evaluated."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        # current weekday+1 (cron-style, 1=Monday in the code's convention)
        dow = now.weekday() + 1
        # a range that includes today
        assert _should_run_now(f"* * * * {dow}-{dow}") is True
        # a range that excludes today (use modular arithmetic to pick a different day)
        other = ((dow + 2) % 7) + 1  # guaranteed != dow when range is [other, other]
        if other != dow:
            assert _should_run_now(f"* * * * {other}-{other}") is False
