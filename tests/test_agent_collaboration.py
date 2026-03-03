"""Tests for WP8: Agent Migration to BaseAgent.

Verifies that all 7 agents conform to the BaseAgent protocol, read/write
signals through SharedContext, and adapt their behaviour based on those
signals (overwhelm, deadline risk, energy configuration, etc.).
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from packages.core.agents.base import BaseAgent
from packages.core.agents import (
    AGENT_REGISTRY,
    ChronosAgent,
    FocusBuddyAgent,
    GuardianAgent,
    LiaisonAgent,
    MentorAgent,
    PlannerAgent,
    ScribeAgent,
)
from packages.core.collaboration.context import SharedContext
from packages.core.models import EnergyConfig, EnergyLevel, UserProfile


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

ALL_AGENT_CLASSES = [
    PlannerAgent,
    ChronosAgent,
    GuardianAgent,
    MentorAgent,
    LiaisonAgent,
    ScribeAgent,
    FocusBuddyAgent,
]

EXPECTED_AGENT_NAMES = {
    "planner",
    "chronos",
    "guardian",
    "mentor",
    "liaison",
    "scribe",
    "focusbuddy",
}


def _make_context(**overrides) -> SharedContext:
    """Build a SharedContext with sensible defaults and optional overrides."""
    defaults = {
        "goal": "Finish quarterly report",
        "tasks": [
            {"title": "Draft outline", "estimate_h": 2},
            {"title": "Write section 1", "estimate_h": 3},
        ],
    }
    defaults.update(overrides)
    return SharedContext(**defaults)


# ---------------------------------------------------------------------------
# 1. All 7 agents extend BaseAgent and expose run / can_contribute
# ---------------------------------------------------------------------------


class TestBaseAgentConformance:
    """Every registered agent must be a BaseAgent subclass with the required
    interface methods."""

    def test_all_seven_agents_are_registered(self):
        for name in EXPECTED_AGENT_NAMES:
            assert name in AGENT_REGISTRY, f"Agent '{name}' is not registered"

    @pytest.mark.parametrize("cls", ALL_AGENT_CLASSES, ids=lambda c: c.name)
    def test_extends_base_agent(self, cls):
        assert issubclass(cls, BaseAgent), f"{cls.__name__} does not extend BaseAgent"

    @pytest.mark.parametrize("cls", ALL_AGENT_CLASSES, ids=lambda c: c.name)
    def test_has_run_method(self, cls):
        assert hasattr(cls, "run"), f"{cls.__name__} is missing run()"
        assert callable(getattr(cls, "run"))

    @pytest.mark.parametrize("cls", ALL_AGENT_CLASSES, ids=lambda c: c.name)
    def test_has_can_contribute_method(self, cls):
        assert hasattr(cls, "can_contribute"), (
            f"{cls.__name__} is missing can_contribute()"
        )
        assert callable(getattr(cls, "can_contribute"))

    @pytest.mark.parametrize("cls", ALL_AGENT_CLASSES, ids=lambda c: c.name)
    def test_has_name_attribute(self, cls):
        agent = cls()
        assert hasattr(agent, "name")
        assert isinstance(agent.name, str)
        assert agent.name != "base", f"{cls.__name__} still has the default 'base' name"


# ---------------------------------------------------------------------------
# 2. Signal reading / writing through SharedContext
# ---------------------------------------------------------------------------


class TestSharedContextSignals:
    """SharedContext.set_signal / get_signal round-trip correctly."""

    def test_set_and_get_signal(self):
        ctx = _make_context()
        ctx.set_signal("test_flag", True)
        assert ctx.get_signal("test_flag") is True

    def test_get_signal_returns_default_when_missing(self):
        ctx = _make_context()
        assert ctx.get_signal("nonexistent") is None
        assert ctx.get_signal("nonexistent", False) is False

    def test_store_and_read_agent_output(self):
        ctx = _make_context()
        ctx.store_output("guardian", {"nudges": 3})
        assert ctx.agent_outputs["guardian"] == {"nudges": 3}

    def test_signals_isolated_between_contexts(self):
        ctx_a = _make_context()
        ctx_b = _make_context()
        ctx_a.set_signal("only_a", True)
        assert ctx_b.get_signal("only_a") is None

    def test_overwrite_signal(self):
        ctx = _make_context()
        ctx.set_signal("flag", 1)
        ctx.set_signal("flag", 2)
        assert ctx.get_signal("flag") == 2


# ---------------------------------------------------------------------------
# 3. can_contribute filtering
# ---------------------------------------------------------------------------


class TestCanContribute:
    """Agents gate themselves via can_contribute(context)."""

    def test_liaison_requires_deadline_at_risk(self):
        agent = LiaisonAgent()

        ctx_safe = _make_context()
        assert agent.can_contribute(ctx_safe) is False, (
            "Liaison should not contribute when deadline_at_risk is absent"
        )

        ctx_risky = _make_context()
        ctx_risky.set_signal("deadline_at_risk", True)
        assert agent.can_contribute(ctx_risky) is True, (
            "Liaison should contribute when deadline_at_risk is True"
        )

    def test_liaison_does_not_contribute_when_deadline_signal_false(self):
        agent = LiaisonAgent()
        ctx = _make_context()
        ctx.set_signal("deadline_at_risk", False)
        assert agent.can_contribute(ctx) is False

    @pytest.mark.parametrize(
        "cls",
        [
            PlannerAgent,
            ChronosAgent,
            GuardianAgent,
            MentorAgent,
            ScribeAgent,
            FocusBuddyAgent,
        ],
        ids=lambda c: c.name,
    )
    def test_always_contributing_agents(self, cls):
        """All agents except Liaison always contribute."""
        agent = cls()
        ctx = _make_context()
        assert agent.can_contribute(ctx) is True


# ---------------------------------------------------------------------------
# 4. Overwhelm flow: Guardian sets signal, Mentor reads it and adapts
# ---------------------------------------------------------------------------


class TestOverwhelmFlow:
    """Guardian detects overwhelm and Mentor adapts its response."""

    @pytest.mark.asyncio
    async def test_guardian_sets_overwhelm_signal(self):
        agent = GuardianAgent()
        profile = UserProfile(overwhelm_threshold=3)
        # 4 tasks exceeds the threshold of 3
        tasks = [{"title": f"Task {i}"} for i in range(4)]
        ctx = _make_context(
            tasks=tasks,
            user_profile=profile,
        )

        await agent.run(ctx)

        assert ctx.get_signal("overwhelm_detected") is True
        assert ctx.get_signal("low_energy_mode") is True

    @pytest.mark.asyncio
    async def test_guardian_no_overwhelm_within_threshold(self):
        agent = GuardianAgent()
        profile = UserProfile(overwhelm_threshold=5)
        tasks = [{"title": f"Task {i}"} for i in range(3)]
        ctx = _make_context(tasks=tasks, user_profile=profile)

        await agent.run(ctx)

        assert ctx.get_signal("overwhelm_detected") is None
        assert ctx.get_signal("low_energy_mode") is None

    @pytest.mark.asyncio
    async def test_mentor_adapts_when_overwhelm_detected(self):
        agent = MentorAgent()
        ctx = _make_context(goal="Learn Rust")
        ctx.set_signal("overwhelm_detected", True)

        result = await agent.run(ctx)

        assert "feels like a lot" in result.lower()
        assert "Learn Rust" in result

    @pytest.mark.asyncio
    async def test_mentor_normal_when_no_overwhelm(self):
        agent = MentorAgent()
        ctx = _make_context(goal="Build app")

        result = await agent.run(ctx)

        # should come from the standard motivate() method
        assert "Build app" in result
        assert "feels like a lot" not in result.lower()

    @pytest.mark.asyncio
    async def test_guardian_then_mentor_end_to_end(self):
        """Full overwhelm flow: Guardian writes signal, Mentor reads it."""
        guardian = GuardianAgent()
        mentor = MentorAgent()

        profile = UserProfile(overwhelm_threshold=2)
        tasks = [{"title": f"T{i}"} for i in range(5)]
        ctx = _make_context(tasks=tasks, user_profile=profile, goal="Ship v2")

        await guardian.run(ctx)
        result = await mentor.run(ctx)

        assert ctx.get_signal("overwhelm_detected") is True
        assert "feels like a lot" in result.lower()
        assert "Ship v2" in result


# ---------------------------------------------------------------------------
# 5. Deadline risk: Chronos sets signal, Liaison reads it
# ---------------------------------------------------------------------------


class TestDeadlineRiskFlow:
    """Chronos flags deadline_at_risk; Liaison reacts."""

    @pytest.mark.asyncio
    async def test_chronos_sets_deadline_at_risk(self):
        agent = ChronosAgent()
        # max_daily_hours is 5 for medium energy => threshold = 5*3=15
        # total_hours = 6*3 = 18 > 15 => deadline at risk
        config = EnergyConfig.for_level(EnergyLevel.medium)
        tasks = [{"title": f"Big task {i}", "estimate_h": 6} for i in range(3)]
        ctx = _make_context(tasks=tasks, energy_config=config)

        await agent.run(ctx)

        assert ctx.get_signal("deadline_at_risk") is True

    @pytest.mark.asyncio
    async def test_chronos_no_risk_when_hours_fit(self):
        agent = ChronosAgent()
        config = EnergyConfig.for_level(EnergyLevel.high)
        tasks = [{"title": "Small task", "estimate_h": 1}]
        ctx = _make_context(tasks=tasks, energy_config=config)

        await agent.run(ctx)

        assert ctx.get_signal("deadline_at_risk") is None

    @pytest.mark.asyncio
    async def test_liaison_drafts_message_when_deadline_at_risk(self):
        agent = LiaisonAgent()
        ctx = _make_context(goal="Launch feature")
        ctx.set_signal("deadline_at_risk", True)

        with patch.object(agent, "draft_message", new_callable=AsyncMock) as mock_draft:
            mock_draft.return_value = {
                "subject": "Help needed",
                "message": "We need help with Launch feature",
                "tone": "professional",
                "estimated_tokens": 42,
                "metadata": {"generation_method": "llm"},
            }
            await agent.run(ctx)

        mock_draft.assert_awaited_once()
        call_kwargs = mock_draft.call_args
        assert call_kwargs[0][0] == "Launch feature"
        assert call_kwargs[1]["message_type"] == "help_request"

    @pytest.mark.asyncio
    async def test_liaison_returns_none_without_deadline_risk(self):
        agent = LiaisonAgent()
        ctx = _make_context(goal="Relax")

        result = await agent.run(ctx)

        assert result is None

    @pytest.mark.asyncio
    async def test_chronos_then_liaison_end_to_end(self):
        """Full deadline risk flow: Chronos flags risk, Liaison responds."""
        chronos = ChronosAgent()
        liaison = LiaisonAgent()

        config = EnergyConfig.for_level(EnergyLevel.low)
        # low energy max_daily_hours=2 => threshold=6; total=12 > 6
        tasks = [{"title": f"Task {i}", "estimate_h": 4} for i in range(3)]
        ctx = _make_context(tasks=tasks, energy_config=config, goal="Migrate DB")

        await chronos.run(ctx)
        assert ctx.get_signal("deadline_at_risk") is True
        assert liaison.can_contribute(ctx) is True

        with patch.object(
            liaison, "draft_message", new_callable=AsyncMock
        ) as mock_draft:
            mock_draft.return_value = {
                "subject": "Help needed",
                "message": "Deadline at risk for Migrate DB",
                "tone": "professional",
                "estimated_tokens": 50,
                "metadata": {"generation_method": "llm"},
            }
            result = await liaison.run(ctx)

        assert result is not None
        assert result["message"] == "Deadline at risk for Migrate DB"


# ---------------------------------------------------------------------------
# 6. FocusBuddy adapts session duration from energy config
# ---------------------------------------------------------------------------


class TestFocusBuddyEnergyAdaptation:
    """FocusBuddy adjusts session_duration_minutes based on energy level."""

    @pytest.mark.asyncio
    async def test_low_energy_short_sessions(self):
        agent = FocusBuddyAgent()
        config = EnergyConfig.for_level(EnergyLevel.low)
        tasks = [{"title": "Read docs"}, {"title": "Take notes"}]
        ctx = _make_context(tasks=tasks, energy_config=config)

        sessions = await agent.run(ctx)

        assert len(sessions) == 2
        for s in sessions:
            assert s["duration_min"] == 15

    @pytest.mark.asyncio
    async def test_medium_energy_standard_sessions(self):
        agent = FocusBuddyAgent()
        config = EnergyConfig.for_level(EnergyLevel.medium)
        tasks = [{"title": "Write code"}]
        ctx = _make_context(tasks=tasks, energy_config=config)

        sessions = await agent.run(ctx)

        assert len(sessions) == 1
        assert sessions[0]["duration_min"] == 25

    @pytest.mark.asyncio
    async def test_high_energy_long_sessions(self):
        agent = FocusBuddyAgent()
        config = EnergyConfig.for_level(EnergyLevel.high)
        tasks = [{"title": "Deep work"}, {"title": "Architecture review"}]
        ctx = _make_context(tasks=tasks, energy_config=config)

        sessions = await agent.run(ctx)

        assert len(sessions) == 2
        for s in sessions:
            assert s["duration_min"] == 50

    @pytest.mark.asyncio
    async def test_empty_tasks_returns_empty(self):
        agent = FocusBuddyAgent()
        ctx = _make_context(tasks=[])

        sessions = await agent.run(ctx)

        assert sessions == []

    @pytest.mark.asyncio
    async def test_session_titles_match_tasks(self):
        agent = FocusBuddyAgent()
        config = EnergyConfig.for_level(EnergyLevel.medium)
        tasks = [{"title": "Alpha"}, {"title": "Beta"}]
        ctx = _make_context(tasks=tasks, energy_config=config)

        sessions = await agent.run(ctx)

        assert sessions[0]["task"] == "Alpha"
        assert sessions[1]["task"] == "Beta"


# ---------------------------------------------------------------------------
# 7. Scribe persists context
# ---------------------------------------------------------------------------


class TestScribePersistence:
    """Scribe records plan data via memory.store."""

    @pytest.mark.asyncio
    async def test_scribe_run_persists_tasks(self, monkeypatch):
        agent = ScribeAgent()
        mock_store = AsyncMock()
        monkeypatch.setattr("packages.core.agents.scribe.memory.store", mock_store)

        tasks = [{"title": "Do laundry"}, {"title": "Buy groceries"}]
        ctx = _make_context(tasks=tasks)

        result = await agent.run(ctx)

        assert result["saved"] is True
        assert result["task_count"] == 2
        assert mock_store.called

    @pytest.mark.asyncio
    async def test_scribe_run_empty_tasks(self, monkeypatch):
        agent = ScribeAgent()
        mock_store = AsyncMock()
        monkeypatch.setattr("packages.core.agents.scribe.memory.store", mock_store)

        ctx = _make_context(tasks=[])

        result = await agent.run(ctx)

        assert result["saved"] is True
        assert result["task_count"] == 0

    @pytest.mark.asyncio
    async def test_scribe_always_contributes(self):
        agent = ScribeAgent()
        ctx = _make_context()
        assert agent.can_contribute(ctx) is True


# ---------------------------------------------------------------------------
# 8. Planner populates context.tasks via run()
# ---------------------------------------------------------------------------


class TestPlannerRun:
    """Planner.run() fills context.tasks from the LLM response."""

    @pytest.mark.asyncio
    async def test_planner_populates_tasks(self, mock_litellm):
        import json

        tasks_json = json.dumps(
            [
                {
                    "id": "1",
                    "title": "Step one",
                    "detail": "First step",
                    "priority": "P1",
                    "estimate_h": 2,
                },
                {
                    "id": "2",
                    "title": "Step two",
                    "detail": "Second step",
                    "priority": "P2",
                    "estimate_h": 3,
                },
            ]
        )

        # build a litellm-shaped mock response
        message = MagicMock()
        message.content = tasks_json
        message.tool_calls = None
        choice = MagicMock()
        choice.message = message
        response = MagicMock()
        response.choices = [choice]
        mock_litellm.return_value = response

        agent = PlannerAgent()
        ctx = _make_context(goal="Build a website")

        with patch("packages.core.agents.planner.memory.store", new_callable=AsyncMock):
            await agent.run(ctx)

        assert len(ctx.tasks) == 2
        assert ctx.tasks[0]["title"] == "Step one"

    @pytest.mark.asyncio
    async def test_planner_always_contributes(self):
        agent = PlannerAgent()
        ctx = _make_context()
        assert agent.can_contribute(ctx) is True


# ---------------------------------------------------------------------------
# 9. Integration: multi-agent signal cascade
# ---------------------------------------------------------------------------


class TestMultiAgentSignalCascade:
    """Verify that signals propagate correctly across multiple agents
    operating on the same SharedContext."""

    @pytest.mark.asyncio
    async def test_overwhelm_cascade_guardian_mentor_focusbuddy(self):
        """Guardian detects overwhelm, Mentor adapts, FocusBuddy uses energy."""
        guardian = GuardianAgent()
        mentor = MentorAgent()
        focusbuddy = FocusBuddyAgent()

        profile = UserProfile(overwhelm_threshold=2)
        config = EnergyConfig.for_level(EnergyLevel.low)
        tasks = [{"title": f"T{i}"} for i in range(5)]
        ctx = _make_context(
            tasks=tasks,
            user_profile=profile,
            energy_config=config,
            goal="Prepare presentation",
        )

        # phase 1: guardian detects overwhelm
        await guardian.run(ctx)
        assert ctx.get_signal("overwhelm_detected") is True

        # phase 2: mentor adapts
        mentor_result = await mentor.run(ctx)
        assert "feels like a lot" in mentor_result.lower()

        # phase 3: focusbuddy creates short sessions for low energy
        sessions = await focusbuddy.run(ctx)
        assert all(s["duration_min"] == 15 for s in sessions)

    @pytest.mark.asyncio
    async def test_deadline_risk_cascade_chronos_liaison_scribe(self, monkeypatch):
        """Chronos sets deadline risk, Liaison drafts message, Scribe persists."""
        chronos = ChronosAgent()
        liaison = LiaisonAgent()
        scribe = ScribeAgent()

        mock_store = AsyncMock()
        monkeypatch.setattr("packages.core.agents.scribe.memory.store", mock_store)

        config = EnergyConfig.for_level(EnergyLevel.low)
        tasks = [{"title": f"Big job {i}", "estimate_h": 5} for i in range(3)]
        ctx = _make_context(
            tasks=tasks,
            energy_config=config,
            goal="Ship product",
        )

        # phase 1: chronos detects risk
        await chronos.run(ctx)
        assert ctx.get_signal("deadline_at_risk") is True

        # phase 2: liaison can now contribute
        assert liaison.can_contribute(ctx) is True

        with patch.object(
            liaison, "draft_message", new_callable=AsyncMock
        ) as mock_draft:
            mock_draft.return_value = {
                "subject": "Risk alert",
                "message": "Deadline risk for Ship product",
                "tone": "professional",
                "estimated_tokens": 30,
                "metadata": {"generation_method": "llm"},
            }
            liaison_result = await liaison.run(ctx)

        assert liaison_result is not None

        # phase 3: scribe persists
        scribe_result = await scribe.run(ctx)
        assert scribe_result["saved"] is True

    @pytest.mark.asyncio
    async def test_no_signals_when_all_within_thresholds(self):
        """When everything is within bounds, no special signals are set."""
        guardian = GuardianAgent()
        chronos = ChronosAgent()
        mentor = MentorAgent()

        profile = UserProfile(overwhelm_threshold=10)
        config = EnergyConfig.for_level(EnergyLevel.high)
        tasks = [{"title": "Easy task", "estimate_h": 1}]
        ctx = _make_context(
            tasks=tasks,
            user_profile=profile,
            energy_config=config,
            goal="Quick win",
        )

        await guardian.run(ctx)
        await chronos.run(ctx)
        mentor_result = await mentor.run(ctx)

        assert ctx.get_signal("overwhelm_detected") is None
        assert ctx.get_signal("deadline_at_risk") is None
        assert "feels like a lot" not in mentor_result.lower()
