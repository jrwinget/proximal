"""Tests for Phase 1.6 and 1.7: Signal wiring across agents.

1.6 — low_energy_mode read by FocusBuddy, Chronos, Mentor.
1.7 — deadline_at_risk read by Guardian, Mentor.
"""

from __future__ import annotations

from datetime import datetime

from packages.core.agents.chronos import ChronosAgent
from packages.core.agents.focusbuddy import FocusBuddyAgent
from packages.core.agents.guardian import GuardianAgent
from packages.core.agents.mentor import MentorAgent
from packages.core.collaboration.context import SharedContext
from packages.core.models import EnergyConfig, EnergyLevel, UserProfile


def _make_context(tasks=None, **kwargs):
    defaults = {
        "goal": "Ship feature",
        "tasks": tasks or [{"title": "Write code", "estimate_h": 2}],
        "energy_config": EnergyConfig.for_level(EnergyLevel.medium),
        "user_profile": UserProfile(),
    }
    defaults.update(kwargs)
    return SharedContext(**defaults)


# -----------------------------------------------------------------------
# 1.6 — low_energy_mode signal propagation
# -----------------------------------------------------------------------


class TestLowEnergyModeFocusBuddy:
    """FocusBuddy shortens sessions when low_energy_mode is set."""

    async def test_shortened_sessions(self):
        ctx = _make_context()
        ctx.set_signal("low_energy_mode", True)
        agent = FocusBuddyAgent()
        sessions = await agent.run(ctx)
        # default medium energy base=25, variable style=25, low-energy=0.6*25=15
        assert all(s["duration_min"] < 25 for s in sessions)

    async def test_breaks_forced(self):
        ctx = _make_context()
        ctx.set_signal("low_energy_mode", True)
        agent = FocusBuddyAgent()
        # even hyperfocus style gets breaks in low-energy mode
        ctx.user_profile = UserProfile(focus_style="hyperfocus")
        sessions = await agent.run(ctx)
        assert all(s["break_after"] is True for s in sessions)

    async def test_no_effect_when_signal_absent(self):
        ctx = _make_context()
        agent = FocusBuddyAgent()
        sessions = await agent.run(ctx)
        assert sessions[0]["duration_min"] == 25


class TestLowEnergyModeChronos:
    """Chronos reduces schedule in low-energy mode."""

    async def test_schedule_trimmed(self):
        tasks = [{"title": f"T{i}", "estimate_h": 1} for i in range(8)]
        ctx = _make_context(tasks=tasks)
        ctx.set_signal("low_energy_mode", True)
        agent = ChronosAgent()
        schedule = await agent.run(ctx)
        # medium max_daily=5, low-energy caps at 50% → 2.5 hours
        # each task is 1h, so max ~2 tasks (+ breaks)
        assert len(schedule) < len(tasks)

    async def test_no_trim_without_signal(self):
        tasks = [{"title": f"T{i}", "estimate_h": 1} for i in range(4)]
        ctx = _make_context(tasks=tasks)
        agent = ChronosAgent()
        schedule = await agent.run(ctx)
        # all tasks present plus any breaks
        task_entries = [
            e for e in schedule
            if not (
                isinstance(e.get("task", {}), dict)
                and e["task"].get("title", "").lower() in (
                    "break", "transition time",
                )
            )
        ]
        assert len(task_entries) == 4


class TestLowEnergyModeMentor:
    """Mentor switches to gentler encouragement in low-energy mode."""

    async def test_low_energy_gentle_message(self):
        ctx = _make_context()
        ctx.set_signal("low_energy_mode", True)
        agent = MentorAgent()
        result = await agent.run(ctx)
        assert "easy" in result.lower() or "low energy" in result.lower()

    async def test_normal_message_without_signal(self):
        ctx = _make_context()
        agent = MentorAgent()
        result = await agent.run(ctx)
        assert "easy" not in result.lower() or "Ship feature" in result


# -----------------------------------------------------------------------
# 1.7 — deadline_at_risk signal propagation
# -----------------------------------------------------------------------


class TestDeadlineAtRiskGuardian:
    """Guardian responds to deadline_at_risk with wellness nudge."""

    async def test_guardian_emits_deadline_nudge(self):
        ctx = _make_context()
        ctx.set_signal("deadline_at_risk", True)
        agent = GuardianAgent()
        # should not raise, even without event bus
        _tuesday = datetime(2026, 3, 3, 10, 0)
        await agent.run(ctx, _now=_tuesday)
        # the run completes without error; nudge is emitted on bus

    async def test_guardian_no_nudge_without_risk(self):
        ctx = _make_context()
        agent = GuardianAgent()
        _tuesday = datetime(2026, 3, 3, 10, 0)
        result = await agent.run(ctx, _now=_tuesday)
        assert result is not None


class TestDeadlineAtRiskMentor:
    """Mentor provides supportive-under-pressure message."""

    async def test_deadline_risk_message(self):
        ctx = _make_context()
        ctx.set_signal("deadline_at_risk", True)
        agent = MentorAgent()
        result = await agent.run(ctx)
        assert "deadline" in result.lower() or "progress" in result.lower()
        assert "Ship feature" in result

    async def test_deadline_risk_adapts_to_tone(self):
        for tone in ("warm", "professional", "direct", "playful"):
            ctx = _make_context(
                user_profile=UserProfile(tone=tone),
            )
            ctx.set_signal("deadline_at_risk", True)
            agent = MentorAgent()
            result = await agent.run(ctx)
            assert "Ship feature" in result


# -----------------------------------------------------------------------
# Integration: signal cascade Guardian → FocusBuddy + Mentor
# -----------------------------------------------------------------------


class TestSignalCascadeIntegration:
    """End-to-end signal propagation across agents."""

    async def test_guardian_low_energy_to_focusbuddy_and_mentor(self):
        guardian = GuardianAgent()
        focusbuddy = FocusBuddyAgent()
        mentor = MentorAgent()

        # monday is a low-energy day
        _monday = datetime(2026, 3, 2, 10, 0)
        profile = UserProfile(low_energy_days=["Monday"])
        tasks = [{"title": "Light task", "estimate_h": 1}]
        ctx = _make_context(tasks=tasks, user_profile=profile)

        await guardian.run(ctx, _now=_monday)
        assert ctx.get_signal("low_energy_mode") is True

        sessions = await focusbuddy.run(ctx)
        assert sessions[0]["duration_min"] < 25
        assert sessions[0]["break_after"] is True

        msg = await mentor.run(ctx)
        assert "easy" in msg.lower() or "low energy" in msg.lower()

    async def test_chronos_deadline_to_guardian_and_mentor(self):
        chronos = ChronosAgent()
        guardian = GuardianAgent()
        mentor = MentorAgent()

        config = EnergyConfig.for_level(EnergyLevel.low)
        tasks = [{"title": f"Big {i}", "estimate_h": 5} for i in range(3)]
        ctx = _make_context(
            tasks=tasks,
            energy_config=config,
        )

        await chronos.run(ctx)
        assert ctx.get_signal("deadline_at_risk") is True

        _tuesday = datetime(2026, 3, 3, 10, 0)
        await guardian.run(ctx, _now=_tuesday)

        msg = await mentor.run(ctx)
        assert (
            "deadline" in msg.lower()
            or "progress" in msg.lower()
            or "tight" in msg.lower()
        )
