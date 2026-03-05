"""Tests for OrchestratorV2 phased execution (WP7)."""

from unittest.mock import patch

import pytest

from packages.core.agents.base import BaseAgent
from packages.core.collaboration.context import SharedContext
from packages.core.models import UserProfile
from packages.core.orchestrator import OrchestratorV2


class MockAgent(BaseAgent):
    """Test agent that records calls."""

    name = "mock"

    def __init__(self, output="result", should_contribute=True):
        self._output = output
        self._should_contribute = should_contribute

    async def run(self, context: SharedContext):
        return self._output

    def can_contribute(self, context: SharedContext) -> bool:
        return self._should_contribute


class SignalAgent(BaseAgent):
    """Test agent that sets a signal."""

    name = "signal_setter"

    async def run(self, context: SharedContext):
        context.set_signal("overwhelm_detected", True)
        return {"signal_set": True}

    def can_contribute(self, context: SharedContext) -> bool:
        return True


class SignalReader(BaseAgent):
    """Test agent that reads signals."""

    name = "signal_reader"

    async def run(self, context: SharedContext):
        overwhelm = context.get_signal("overwhelm_detected", False)
        return {"saw_overwhelm": overwhelm}

    def can_contribute(self, context: SharedContext) -> bool:
        return True


def _make_agent_class(name, output, should_contribute=True):
    """Build a BaseAgent subclass that returns a fixed output."""

    class _Agent(BaseAgent):
        async def run(self, context):
            return output

        def can_contribute(self, context):
            return should_contribute

    _Agent.name = name
    _Agent.__qualname__ = f"_Agent_{name}"
    return _Agent


class TestOrchestratorV2:
    @pytest.mark.asyncio
    async def test_basic_run(self):
        """Full 5-phase run completes and returns a SharedContext."""
        orch = OrchestratorV2()

        registry = {
            "planner": _make_agent_class("planner", [{"title": "Task 1"}]),
            "guardian": _make_agent_class("guardian", {"wellness": "ok"}),
            "chronos": _make_agent_class("chronos", {"schedule": []}),
            "mentor": _make_agent_class("mentor", "Keep going!"),
            "liaison": _make_agent_class("liaison", None),
            "focusbuddy": _make_agent_class("focusbuddy", []),
            "scribe": _make_agent_class("scribe", {"saved": True}),
        }

        with patch.dict(orch.registry, registry, clear=True):
            ctx = await orch.run("test goal")

        assert isinstance(ctx, SharedContext)
        assert ctx.goal == "test goal"
        assert "planner" in ctx.agent_outputs
        assert "guardian" in ctx.agent_outputs
        assert "scribe" in ctx.agent_outputs

    @pytest.mark.asyncio
    async def test_run_returns_shared_context_with_energy(self):
        """Energy level is propagated to the SharedContext."""
        orch = OrchestratorV2()

        registry = {
            "planner": _make_agent_class("planner", []),
            "guardian": _make_agent_class("guardian", {}),
            "chronos": _make_agent_class("chronos", {}),
            "mentor": _make_agent_class("mentor", ""),
            "liaison": _make_agent_class("liaison", None),
            "focusbuddy": _make_agent_class("focusbuddy", []),
            "scribe": _make_agent_class("scribe", {}),
        }

        with patch.dict(orch.registry, registry, clear=True):
            ctx = await orch.run("test goal", energy_level="low")

        assert ctx.energy_level == "low"
        assert ctx.energy_config.tone == "gentle"

    @pytest.mark.asyncio
    async def test_agent_opt_out(self):
        """Agents that return False from can_contribute are skipped."""
        orch = OrchestratorV2()

        registry = {
            "planner": _make_agent_class("planner", []),
            "guardian": _make_agent_class(
                "guardian", "should not appear", should_contribute=False
            ),
            "chronos": _make_agent_class("chronos", {"schedule": []}),
            "mentor": _make_agent_class("mentor", ""),
            "liaison": _make_agent_class("liaison", None),
            "focusbuddy": _make_agent_class("focusbuddy", []),
            "scribe": _make_agent_class("scribe", {}),
        }

        with patch.dict(orch.registry, registry, clear=True):
            ctx = await orch.run("test goal")

        # guardian opted out, so it should not be in agent_outputs
        assert "guardian" not in ctx.agent_outputs

    @pytest.mark.asyncio
    async def test_signal_propagation(self):
        """Signals set in one phase should be visible in later phases."""
        ctx = SharedContext(goal="test")

        setter = SignalAgent()
        await setter.run(ctx)

        reader = SignalReader()
        result = await reader.run(ctx)

        assert result["saw_overwhelm"] is True

    @pytest.mark.asyncio
    async def test_signal_propagation_across_phases(self):
        """Signals set by guardian in phase 2 are visible to mentor in phase 3."""
        orch = OrchestratorV2()

        class GuardianSignaler(BaseAgent):
            name = "guardian"

            async def run(self, context):
                context.set_signal("overwhelm_detected", True)
                return {"overwhelm": True}

            def can_contribute(self, context):
                return True

        class MentorReader(BaseAgent):
            name = "mentor"

            async def run(self, context):
                return {
                    "saw_overwhelm": context.get_signal("overwhelm_detected", False)
                }

            def can_contribute(self, context):
                return True

        registry = {
            "planner": _make_agent_class("planner", []),
            "guardian": GuardianSignaler,
            "chronos": _make_agent_class("chronos", {}),
            "mentor": MentorReader,
            "liaison": _make_agent_class("liaison", None),
            "focusbuddy": _make_agent_class("focusbuddy", []),
            "scribe": _make_agent_class("scribe", {}),
        }

        with patch.dict(orch.registry, registry, clear=True):
            ctx = await orch.run("overwhelming goal")

        assert ctx.agent_outputs["guardian"] == {"overwhelm": True}
        assert ctx.agent_outputs["mentor"]["saw_overwhelm"] is True

    @pytest.mark.asyncio
    async def test_fault_tolerance(self):
        """A failing agent does not crash the pipeline; its output is None."""
        orch = OrchestratorV2()

        class FailingAgent(BaseAgent):
            name = "failing"

            async def run(self, context):
                raise RuntimeError("boom")

            def can_contribute(self, context):
                return True

        registry = {
            "planner": _make_agent_class("planner", "ok"),
            "guardian": FailingAgent,
            "chronos": _make_agent_class("chronos", "ok"),
            "mentor": _make_agent_class("mentor", "ok"),
            "liaison": _make_agent_class("liaison", "ok"),
            "focusbuddy": _make_agent_class("focusbuddy", "ok"),
            "scribe": _make_agent_class("scribe", "ok"),
        }

        with patch.dict(orch.registry, registry, clear=True):
            ctx = await orch.run("test goal")

        assert ctx.agent_outputs.get("guardian") is None
        assert ctx.agent_outputs.get("planner") == "ok"

    @pytest.mark.asyncio
    async def test_missing_agent_skipped(self):
        """If a phase references an agent not in the registry, it is skipped."""
        orch = OrchestratorV2()

        # only register planner and scribe; everything else missing
        registry = {
            "planner": _make_agent_class("planner", "plan"),
            "scribe": _make_agent_class("scribe", "saved"),
        }

        with patch.dict(orch.registry, registry, clear=True):
            ctx = await orch.run("sparse goal")

        assert ctx.agent_outputs.get("planner") == "plan"
        assert ctx.agent_outputs.get("scribe") == "saved"
        assert "guardian" not in ctx.agent_outputs

    @pytest.mark.asyncio
    async def test_user_profile_passed(self):
        """A custom UserProfile is stored in the context."""
        orch = OrchestratorV2()

        profile = UserProfile(name="Tester", tone="direct")

        registry = {
            "planner": _make_agent_class("planner", []),
            "guardian": _make_agent_class("guardian", {}),
            "chronos": _make_agent_class("chronos", {}),
            "mentor": _make_agent_class("mentor", ""),
            "liaison": _make_agent_class("liaison", None),
            "focusbuddy": _make_agent_class("focusbuddy", []),
            "scribe": _make_agent_class("scribe", {}),
        }

        with patch.dict(orch.registry, registry, clear=True):
            ctx = await orch.run("profile goal", user_profile=profile)

        assert ctx.user_profile.name == "Tester"
        assert ctx.user_profile.tone == "direct"

    @pytest.mark.asyncio
    async def test_run_phase_empty_returns_empty_dict(self):
        """_run_phase with no valid agents returns an empty dict."""
        orch = OrchestratorV2()
        ctx = SharedContext(goal="test")

        with patch.dict(orch.registry, {}, clear=True):
            result = await orch._run_phase("empty", ["nonexistent"], ctx)

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_agent_raises_for_unknown(self):
        """_get_agent raises ValueError for unregistered names."""
        orch = OrchestratorV2()

        with patch.dict(orch.registry, {}, clear=True):
            with pytest.raises(ValueError, match="not found"):
                orch._get_agent("unknown")
