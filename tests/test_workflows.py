"""Tests for workflow definition models, built-in workflows, executor, and checkpoints."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from packages.core.workflows.definition import (
    CheckpointPolicy,
    TriggerType,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowTrigger,
)
from packages.core.workflows.builtins import BUILTIN_WORKFLOWS
from packages.core.workflows.executor import WorkflowExecutor, WorkflowExecution
from packages.core.workflows.checkpoints import CheckpointManager


# ---------------------------------------------------------------------------
# WorkflowTrigger model
# ---------------------------------------------------------------------------


class TestWorkflowTrigger:
    """Tests for the WorkflowTrigger model."""

    def test_default_trigger_is_manual(self):
        """A bare trigger should default to manual type."""
        trigger = WorkflowTrigger()
        assert trigger.trigger_type == TriggerType.manual
        assert trigger.cron_expression == ""
        assert trigger.event_topic == ""

    def test_cron_trigger(self):
        """Cron trigger should store the expression."""
        trigger = WorkflowTrigger(
            trigger_type=TriggerType.cron,
            cron_expression="0 9 * * 1-5",
        )
        assert trigger.trigger_type == TriggerType.cron
        assert trigger.cron_expression == "0 9 * * 1-5"

    def test_event_trigger(self):
        """Event trigger should store the topic."""
        trigger = WorkflowTrigger(
            trigger_type=TriggerType.event,
            event_topic="guardian.nudge",
        )
        assert trigger.trigger_type == TriggerType.event
        assert trigger.event_topic == "guardian.nudge"

    def test_trigger_type_values(self):
        """TriggerType should expose cron, event, and manual."""
        assert TriggerType.cron == "cron"
        assert TriggerType.event == "event"
        assert TriggerType.manual == "manual"
        assert len(TriggerType) == 3


# ---------------------------------------------------------------------------
# CheckpointPolicy model
# ---------------------------------------------------------------------------


class TestCheckpointPolicy:
    """Tests for the CheckpointPolicy enum."""

    def test_values(self):
        """All four checkpoint policies should exist."""
        assert CheckpointPolicy.none == "none"
        assert CheckpointPolicy.before_send == "before_send"
        assert CheckpointPolicy.before_external == "before_external"
        assert CheckpointPolicy.every_step == "every_step"

    def test_membership(self):
        """Should have exactly four members."""
        assert len(CheckpointPolicy) == 4

    def test_is_str_enum(self):
        """CheckpointPolicy members should be usable as plain strings."""
        assert isinstance(CheckpointPolicy.none, str)
        assert f"policy={CheckpointPolicy.before_send}" == "policy=before_send"


# ---------------------------------------------------------------------------
# WorkflowStep model
# ---------------------------------------------------------------------------


class TestWorkflowStep:
    """Tests for the WorkflowStep model."""

    def test_minimal_step(self):
        """A step with only name and agent should get sensible defaults."""
        step = WorkflowStep(name="test_step", agent="chronos")
        assert step.name == "test_step"
        assert step.agent == "chronos"
        assert step.method == "run"
        assert step.args == {}
        assert step.timeout_seconds == 30.0
        assert step.checkpoint == CheckpointPolicy.none

    def test_full_step(self):
        """All fields should be assignable."""
        step = WorkflowStep(
            name="draft",
            agent="liaison",
            method="draft_message",
            args={"template": "status"},
            timeout_seconds=60.0,
            checkpoint=CheckpointPolicy.before_send,
        )
        assert step.method == "draft_message"
        assert step.args == {"template": "status"}
        assert step.timeout_seconds == 60.0
        assert step.checkpoint == CheckpointPolicy.before_send

    def test_step_serialization(self):
        """Step should round-trip through dict."""
        step = WorkflowStep(name="s1", agent="guardian", method="add_nudges")
        data = step.model_dump()
        restored = WorkflowStep.model_validate(data)
        assert restored == step


# ---------------------------------------------------------------------------
# WorkflowDefinition model
# ---------------------------------------------------------------------------


class TestWorkflowDefinition:
    """Tests for the WorkflowDefinition model."""

    def test_minimal_definition(self):
        """A workflow with just a name should get safe defaults."""
        wf = WorkflowDefinition(name="test_wf")
        assert wf.name == "test_wf"
        assert wf.description == ""
        assert wf.trigger.trigger_type == TriggerType.manual
        assert wf.steps == []
        assert wf.max_auto_runs_per_day == 10
        assert wf.enabled is True

    def test_full_definition(self):
        """All fields should be assignable."""
        wf = WorkflowDefinition(
            name="my_workflow",
            description="A custom workflow",
            trigger=WorkflowTrigger(
                trigger_type=TriggerType.cron,
                cron_expression="0 8 * * *",
            ),
            steps=[
                WorkflowStep(name="step1", agent="chronos"),
                WorkflowStep(name="step2", agent="guardian"),
            ],
            max_auto_runs_per_day=3,
            enabled=False,
        )
        assert wf.description == "A custom workflow"
        assert len(wf.steps) == 2
        assert wf.max_auto_runs_per_day == 3
        assert wf.enabled is False

    def test_definition_serialization(self):
        """WorkflowDefinition should round-trip through dict."""
        wf = WorkflowDefinition(
            name="rt",
            steps=[WorkflowStep(name="s", agent="scribe", method="record_plan")],
        )
        data = wf.model_dump()
        restored = WorkflowDefinition.model_validate(data)
        assert restored.name == wf.name
        assert len(restored.steps) == len(wf.steps)
        assert restored.steps[0].agent == "scribe"


# ---------------------------------------------------------------------------
# Built-in workflow definitions
# ---------------------------------------------------------------------------


class TestBuiltinWorkflows:
    """Tests for the built-in workflow catalogue."""

    def test_four_builtins_exist(self):
        """There should be exactly four built-in workflows."""
        assert len(BUILTIN_WORKFLOWS) == 4

    def test_expected_names(self):
        """Built-in names should match the expected set."""
        expected = {
            "daily_planning",
            "proactive_checkin",
            "weekly_status",
            "adaptive_learning",
        }
        assert set(BUILTIN_WORKFLOWS.keys()) == expected

    def test_daily_planning(self):
        """Daily planning should be cron-triggered with three steps."""
        wf = BUILTIN_WORKFLOWS["daily_planning"]
        assert wf.trigger.trigger_type == TriggerType.cron
        assert wf.trigger.cron_expression == "0 17 * * 1-5"
        assert len(wf.steps) == 3
        assert wf.max_auto_runs_per_day == 1

    def test_proactive_checkin(self):
        """Proactive check-in should be event-triggered."""
        wf = BUILTIN_WORKFLOWS["proactive_checkin"]
        assert wf.trigger.trigger_type == TriggerType.event
        assert wf.trigger.event_topic == "guardian.nudge"
        assert len(wf.steps) == 1
        assert wf.max_auto_runs_per_day == 5

    def test_weekly_status_has_checkpoint(self):
        """Weekly status draft_status step should require approval."""
        wf = BUILTIN_WORKFLOWS["weekly_status"]
        draft_step = next(s for s in wf.steps if s.name == "draft_status")
        assert draft_step.checkpoint == CheckpointPolicy.before_send

    def test_adaptive_learning(self):
        """Adaptive learning should run weekly on Sunday."""
        wf = BUILTIN_WORKFLOWS["adaptive_learning"]
        assert wf.trigger.trigger_type == TriggerType.cron
        assert "0" in wf.trigger.cron_expression.split()[-1]  # day-of-week 0 (Sunday)
        assert wf.max_auto_runs_per_day == 1

    def test_all_builtins_enabled(self):
        """All built-in workflows should be enabled by default."""
        for name, wf in BUILTIN_WORKFLOWS.items():
            assert wf.enabled is True, f"{name} should be enabled"


# ---------------------------------------------------------------------------
# WorkflowExecution
# ---------------------------------------------------------------------------


class TestWorkflowExecution:
    """Tests for the WorkflowExecution tracking object."""

    def test_initial_state(self):
        """A new execution should start in 'pending' state."""
        wf = WorkflowDefinition(name="test")
        execution = WorkflowExecution(wf)
        assert execution.status == "pending"
        assert execution.started_at is None
        assert execution.completed_at is None
        assert execution.step_results == {}
        assert execution.error is None

    def test_to_dict(self):
        """to_dict should include all fields."""
        wf = WorkflowDefinition(name="test")
        execution = WorkflowExecution(wf)
        d = execution.to_dict()
        assert d["workflow_name"] == "test"
        assert d["status"] == "pending"
        assert d["started_at"] is None
        assert d["step_results"] == {}
        assert d["error"] is None


# ---------------------------------------------------------------------------
# WorkflowExecutor — happy path
# ---------------------------------------------------------------------------


def _make_mock_agent(method_name: str, return_value="ok"):
    """Create a mock agent class whose method returns the given value."""
    agent_instance = MagicMock()
    mock_method = AsyncMock(return_value=return_value)
    setattr(agent_instance, method_name, mock_method)
    agent_cls = MagicMock(return_value=agent_instance)
    return agent_cls, mock_method


class TestWorkflowExecutorHappyPath:
    """Tests for WorkflowExecutor running steps in sequence."""

    @pytest.mark.asyncio
    async def test_runs_all_steps_sequentially(self):
        """Executor should call each step agent method in order."""
        agent_cls_a, method_a = _make_mock_agent("do_a", return_value="result_a")
        agent_cls_b, method_b = _make_mock_agent("do_b", return_value="result_b")

        registry = {"agent_a": agent_cls_a, "agent_b": agent_cls_b}

        wf = WorkflowDefinition(
            name="seq_test",
            steps=[
                WorkflowStep(name="step_a", agent="agent_a", method="do_a"),
                WorkflowStep(name="step_b", agent="agent_b", method="do_b"),
            ],
        )

        executor = WorkflowExecutor()
        with patch("packages.core.workflows.executor.AGENT_REGISTRY", registry):
            execution = await executor.execute(wf)

        assert execution.status == "completed"
        assert execution.step_results["step_a"] == "result_a"
        assert execution.step_results["step_b"] == "result_b"
        assert execution.started_at is not None
        assert execution.completed_at is not None
        method_a.assert_awaited_once()
        method_b.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_empty_workflow_completes(self):
        """A workflow with no steps should complete successfully."""
        wf = WorkflowDefinition(name="empty")
        executor = WorkflowExecutor()
        execution = await executor.execute(wf)
        assert execution.status == "completed"
        assert execution.step_results == {}


# ---------------------------------------------------------------------------
# WorkflowExecutor — failure handling
# ---------------------------------------------------------------------------


class TestWorkflowExecutorFailures:
    """Tests for executor handling of step failures."""

    @pytest.mark.asyncio
    async def test_missing_agent_fails_gracefully(self):
        """If an agent is not in the registry the workflow should fail."""
        wf = WorkflowDefinition(
            name="missing_agent",
            steps=[WorkflowStep(name="s1", agent="nonexistent", method="run")],
        )
        executor = WorkflowExecutor()
        with patch("packages.core.workflows.executor.AGENT_REGISTRY", {}):
            execution = await executor.execute(wf)

        assert execution.status == "failed"
        assert "not found" in execution.error

    @pytest.mark.asyncio
    async def test_missing_method_fails_gracefully(self):
        """If the agent lacks the requested method the workflow should fail."""
        agent_instance = MagicMock(spec=[])  # no attributes
        agent_cls = MagicMock(return_value=agent_instance)
        registry = {"agent_x": agent_cls}

        wf = WorkflowDefinition(
            name="missing_method",
            steps=[WorkflowStep(name="s1", agent="agent_x", method="nonexistent")],
        )
        executor = WorkflowExecutor()
        with patch("packages.core.workflows.executor.AGENT_REGISTRY", registry):
            execution = await executor.execute(wf)

        assert execution.status == "failed"
        assert (
            "no method" in execution.error.lower() or "nonexistent" in execution.error
        )

    @pytest.mark.asyncio
    async def test_step_exception_fails_workflow(self):
        """A step that raises should cause the workflow to fail without crashing."""
        agent_instance = MagicMock()
        agent_instance.boom = AsyncMock(side_effect=RuntimeError("kaboom"))
        agent_cls = MagicMock(return_value=agent_instance)
        registry = {"agent_boom": agent_cls}

        wf = WorkflowDefinition(
            name="boom_wf",
            steps=[WorkflowStep(name="boom_step", agent="agent_boom", method="boom")],
        )
        executor = WorkflowExecutor()
        with patch("packages.core.workflows.executor.AGENT_REGISTRY", registry):
            execution = await executor.execute(wf)

        assert execution.status == "failed"
        assert "kaboom" in execution.error
        assert execution.completed_at is not None

    @pytest.mark.asyncio
    async def test_second_step_failure_preserves_first_result(self):
        """If the second step fails, the first step's result should still be recorded."""
        agent_cls_ok, _ = _make_mock_agent("run_ok", return_value="good")
        agent_instance_bad = MagicMock()
        agent_instance_bad.run_bad = AsyncMock(side_effect=ValueError("bad step"))
        agent_cls_bad = MagicMock(return_value=agent_instance_bad)
        registry = {"ok_agent": agent_cls_ok, "bad_agent": agent_cls_bad}

        wf = WorkflowDefinition(
            name="partial",
            steps=[
                WorkflowStep(name="good_step", agent="ok_agent", method="run_ok"),
                WorkflowStep(name="bad_step", agent="bad_agent", method="run_bad"),
            ],
        )
        executor = WorkflowExecutor()
        with patch("packages.core.workflows.executor.AGENT_REGISTRY", registry):
            execution = await executor.execute(wf)

        assert execution.status == "failed"
        assert execution.step_results["good_step"] == "good"
        assert "bad_step" not in execution.step_results


# ---------------------------------------------------------------------------
# WorkflowExecutor — checkpoint approval gates
# ---------------------------------------------------------------------------


class TestWorkflowExecutorCheckpoints:
    """Tests for executor respecting checkpoint approval gates."""

    @pytest.mark.asyncio
    async def test_approved_checkpoint_continues(self):
        """When the approval callback returns True the step should execute."""
        agent_cls, method = _make_mock_agent("draft", return_value="message")
        registry = {"liaison": agent_cls}

        approval_cb = AsyncMock(return_value=True)

        wf = WorkflowDefinition(
            name="approved_wf",
            steps=[
                WorkflowStep(
                    name="draft_step",
                    agent="liaison",
                    method="draft",
                    checkpoint=CheckpointPolicy.before_send,
                ),
            ],
        )
        executor = WorkflowExecutor(approval_callback=approval_cb)
        with patch("packages.core.workflows.executor.AGENT_REGISTRY", registry):
            execution = await executor.execute(wf)

        assert execution.status == "completed"
        assert execution.step_results["draft_step"] == "message"
        approval_cb.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_denied_checkpoint_pauses(self):
        """When the approval callback returns False the workflow should pause."""
        agent_cls, method = _make_mock_agent("draft", return_value="message")
        registry = {"liaison": agent_cls}

        approval_cb = AsyncMock(return_value=False)

        wf = WorkflowDefinition(
            name="denied_wf",
            steps=[
                WorkflowStep(
                    name="draft_step",
                    agent="liaison",
                    method="draft",
                    checkpoint=CheckpointPolicy.before_send,
                ),
            ],
        )
        executor = WorkflowExecutor(approval_callback=approval_cb)
        with patch("packages.core.workflows.executor.AGENT_REGISTRY", registry):
            execution = await executor.execute(wf)

        assert execution.status == "paused"
        assert "awaiting approval" in execution.error
        # the step should not have been executed
        assert "draft_step" not in execution.step_results
        method.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_no_callback_skips_checkpoint(self):
        """When no approval callback is set, checkpoints should be ignored."""
        agent_cls, method = _make_mock_agent("draft", return_value="message")
        registry = {"liaison": agent_cls}

        wf = WorkflowDefinition(
            name="no_cb_wf",
            steps=[
                WorkflowStep(
                    name="draft_step",
                    agent="liaison",
                    method="draft",
                    checkpoint=CheckpointPolicy.before_send,
                ),
            ],
        )
        executor = WorkflowExecutor(approval_callback=None)
        with patch("packages.core.workflows.executor.AGENT_REGISTRY", registry):
            execution = await executor.execute(wf)

        assert execution.status == "completed"
        assert execution.step_results["draft_step"] == "message"

    @pytest.mark.asyncio
    async def test_checkpoint_none_does_not_call_callback(self):
        """Steps with checkpoint=none should never invoke the approval callback."""
        agent_cls, _ = _make_mock_agent("run", return_value="done")
        registry = {"myagent": agent_cls}

        approval_cb = AsyncMock(return_value=True)

        wf = WorkflowDefinition(
            name="no_checkpoint_wf",
            steps=[
                WorkflowStep(
                    name="plain_step",
                    agent="myagent",
                    method="run",
                    checkpoint=CheckpointPolicy.none,
                ),
            ],
        )
        executor = WorkflowExecutor(approval_callback=approval_cb)
        with patch("packages.core.workflows.executor.AGENT_REGISTRY", registry):
            execution = await executor.execute(wf)

        assert execution.status == "completed"
        approval_cb.assert_not_awaited()


# ---------------------------------------------------------------------------
# CheckpointManager
# ---------------------------------------------------------------------------


class TestCheckpointManager:
    """Tests for human-in-the-loop CheckpointManager."""

    def test_initial_state(self):
        """Manager should have no pending approvals initially."""
        mgr = CheckpointManager()
        assert mgr.pending_approvals == []

    @pytest.mark.asyncio
    async def test_auto_approve(self):
        """With auto_approve enabled, approval should return True immediately."""
        mgr = CheckpointManager()
        mgr.set_auto_approve(True)
        step = WorkflowStep(name="auto_step", agent="guardian")
        result = await mgr.request_approval(step)
        assert result is True
        # nothing should be pending
        assert mgr.pending_approvals == []

    @pytest.mark.asyncio
    async def test_approve_flow(self):
        """Approving a pending step should resolve the future to True."""
        mgr = CheckpointManager()
        step = WorkflowStep(name="review_step", agent="liaison")

        # start the approval request as a background task
        task = asyncio.create_task(mgr.request_approval(step))
        # yield control so the request registers
        await asyncio.sleep(0)

        assert "review_step" in mgr.pending_approvals
        ok = mgr.approve("review_step")
        assert ok is True

        result = await task
        assert result is True
        assert mgr.pending_approvals == []

    @pytest.mark.asyncio
    async def test_deny_flow(self):
        """Denying a pending step should resolve the future to False."""
        mgr = CheckpointManager()
        step = WorkflowStep(name="deny_step", agent="liaison")

        task = asyncio.create_task(mgr.request_approval(step))
        await asyncio.sleep(0)

        assert "deny_step" in mgr.pending_approvals
        ok = mgr.deny("deny_step")
        assert ok is True

        result = await task
        assert result is False
        assert mgr.pending_approvals == []

    def test_approve_nonexistent_step(self):
        """Approving a step that is not pending should return False."""
        mgr = CheckpointManager()
        assert mgr.approve("ghost") is False

    def test_deny_nonexistent_step(self):
        """Denying a step that is not pending should return False."""
        mgr = CheckpointManager()
        assert mgr.deny("ghost") is False

    @pytest.mark.asyncio
    async def test_multiple_pending_approvals(self):
        """Multiple steps can be pending at the same time."""
        mgr = CheckpointManager()
        step_a = WorkflowStep(name="step_a", agent="liaison")
        step_b = WorkflowStep(name="step_b", agent="liaison")

        task_a = asyncio.create_task(mgr.request_approval(step_a))
        task_b = asyncio.create_task(mgr.request_approval(step_b))
        await asyncio.sleep(0)

        assert set(mgr.pending_approvals) == {"step_a", "step_b"}

        mgr.approve("step_a")
        mgr.deny("step_b")

        assert await task_a is True
        assert await task_b is False
        assert mgr.pending_approvals == []
