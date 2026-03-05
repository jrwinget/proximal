"""Tests for Phase 1.1: FocusBuddy uses preferred_session_minutes and focus_style."""

from __future__ import annotations


from packages.core.agents.focusbuddy import FocusBuddyAgent
from packages.core.collaboration.context import SharedContext
from packages.core.models import EnergyConfig, EnergyLevel, UserProfile


def _make_context(tasks=None, **profile_kwargs):
    profile = UserProfile(**profile_kwargs)
    energy = EnergyConfig.for_level(EnergyLevel.medium)
    return SharedContext(
        goal="Test",
        tasks=tasks or [{"title": "A"}, {"title": "B"}],
        user_profile=profile,
        energy_config=energy,
    )


class TestFocusBuddyPreferredMinutes:
    """preferred_session_minutes overrides energy_config default."""

    async def test_preferred_session_minutes_used(self):
        ctx = _make_context(preferred_session_minutes=40)
        agent = FocusBuddyAgent()
        sessions = await agent.run(ctx)
        assert all(s["duration_min"] >= 40 for s in sessions)

    async def test_preferred_clamped_to_energy_ceiling(self):
        # medium energy max_task_duration_minutes=45; preference=90 → 45
        ctx = _make_context(preferred_session_minutes=90)
        agent = FocusBuddyAgent()
        sessions = await agent.run(ctx)
        # variable style uses base as-is, capped at 45
        assert all(s["duration_min"] == 45 for s in sessions)

    async def test_energy_floor_respected(self):
        # high energy session=50, default preferred=25 → base=50
        energy = EnergyConfig.for_level(EnergyLevel.high)
        ctx = SharedContext(
            goal="Test",
            tasks=[{"title": "A"}],
            user_profile=UserProfile(),
            energy_config=energy,
        )
        agent = FocusBuddyAgent()
        sessions = await agent.run(ctx)
        assert sessions[0]["duration_min"] == 50

    async def test_default_profile_unchanged(self):
        # default preferred_session_minutes=25, medium energy session=25
        ctx = _make_context()
        agent = FocusBuddyAgent()
        sessions = await agent.run(ctx)
        # variable style uses base as-is → 25
        assert sessions[0]["duration_min"] == 25


class TestFocusBuddyFocusStyle:
    """focus_style produces measurably different session structures."""

    async def test_focus_style_hyperfocus(self):
        ctx = _make_context(focus_style="hyperfocus")
        agent = FocusBuddyAgent()
        sessions = await agent.run(ctx)
        for s in sessions:
            assert s["duration_min"] == int(25 * 1.5)  # 37
            assert s["break_after"] is False
            assert s["check_in"] is False

    async def test_focus_style_variable(self):
        ctx = _make_context(focus_style="variable")
        agent = FocusBuddyAgent()
        sessions = await agent.run(ctx)
        for s in sessions:
            assert s["duration_min"] == 25
            assert s["break_after"] is True
            assert s["check_in"] is True

    async def test_focus_style_short_burst(self):
        ctx = _make_context(focus_style="short-burst")
        agent = FocusBuddyAgent()
        sessions = await agent.run(ctx)
        for s in sessions:
            assert s["duration_min"] == max(10, int(25 * 0.6))  # 15
            assert s["break_after"] is True
            assert s["check_in"] is False

    async def test_short_burst_minimum_10(self):
        # very low preferred → still at least 10
        ctx = _make_context(
            focus_style="short-burst",
            preferred_session_minutes=10,
        )
        agent = FocusBuddyAgent()
        sessions = await agent.run(ctx)
        assert all(s["duration_min"] >= 10 for s in sessions)

    async def test_focus_style_in_session_dict(self):
        for style in ("hyperfocus", "variable", "short-burst"):
            ctx = _make_context(focus_style=style)
            agent = FocusBuddyAgent()
            sessions = await agent.run(ctx)
            assert all(s["focus_style"] == style for s in sessions)

    async def test_unknown_style_falls_back_to_variable(self):
        ctx = _make_context(focus_style="unknown")
        agent = FocusBuddyAgent()
        sessions = await agent.run(ctx)
        assert sessions[0]["break_after"] is True
        assert sessions[0]["check_in"] is True
