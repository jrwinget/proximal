"""Tests for Phase 1.2: Chronos uses peak_hours and time_blindness."""

from __future__ import annotations


from packages.core.agents.chronos import ChronosAgent
from packages.core.collaboration.context import SharedContext
from packages.core.models import EnergyConfig, EnergyLevel, UserProfile


def _make_context(tasks=None, **profile_kwargs):
    profile = UserProfile(**profile_kwargs)
    energy = EnergyConfig.for_level(EnergyLevel.medium)
    return SharedContext(
        goal="Test",
        tasks=tasks or [
            {"title": "High prio", "priority": "P0", "estimate_h": 1},
            {"title": "Low prio", "priority": "P3", "estimate_h": 1},
            {"title": "Med prio", "priority": "P2", "estimate_h": 1},
        ],
        user_profile=profile,
        energy_config=energy,
    )


class TestChronosPeakHours:
    """peak_hours influences task placement in schedule."""

    async def test_peak_hours_scheduling(self):
        # default schedule starts at 09:00; peak at 10 means second slot
        ctx = _make_context(peak_hours=[10, 11])
        agent = ChronosAgent()
        schedule = await agent.run(ctx)

        # find what's in the 10:00 slot
        ten_slot = [
            e for e in schedule
            if e.get("start") == "10:00"
        ]
        assert len(ten_slot) > 0
        # the high-priority task should be in a peak slot
        task_data = ten_slot[0].get("task", {})
        title = (
            task_data.get("title", "")
            if isinstance(task_data, dict)
            else str(task_data)
        )
        assert title == "High prio"

    async def test_no_peak_hours_no_reorder(self):
        ctx = _make_context(peak_hours=[])
        agent = ChronosAgent()
        schedule = await agent.run(ctx)
        # first non-break entry should be original order
        titles = [
            e["task"].get("title", "")
            if isinstance(e["task"], dict) else e["task"]
            for e in schedule
            if not (
                isinstance(e.get("task", {}), dict)
                and e["task"].get("title", "").lower() == "break"
            )
        ]
        assert titles[0] == "High prio"


class TestChronosTimeBlindness:
    """time_blindness affects schedule buffers and notes."""

    async def test_time_blindness_low_no_buffer(self):
        ctx = _make_context(time_blindness="low")
        agent = ChronosAgent()
        schedule = await agent.run(ctx)
        # no transition time entries
        transitions = [
            e for e in schedule
            if isinstance(e.get("task", {}), dict)
            and e["task"].get("title", "") == "Transition time"
        ]
        assert len(transitions) == 0
        # no time_note keys
        assert not any("time_note" in e for e in schedule)

    async def test_time_blindness_moderate_adds_buffer(self):
        ctx = _make_context(time_blindness="moderate")
        agent = ChronosAgent()
        schedule = await agent.run(ctx)
        # should have time notes on task entries
        task_entries = [
            e for e in schedule
            if isinstance(e.get("task", {}), dict)
            and e["task"].get("title", "").lower() not in (
                "break", "transition time",
            )
        ]
        assert all("time_note" in e for e in task_entries)

    async def test_time_blindness_high_adds_transitions(self):
        ctx = _make_context(time_blindness="high")
        agent = ChronosAgent()
        schedule = await agent.run(ctx)
        transitions = [
            e for e in schedule
            if isinstance(e.get("task", {}), dict)
            and e["task"].get("title", "") == "Transition time"
        ]
        # at least one transition between tasks
        assert len(transitions) > 0

    async def test_time_note_content(self):
        ctx = _make_context(time_blindness="moderate")
        agent = ChronosAgent()
        schedule = await agent.run(ctx)
        task_entries = [
            e for e in schedule
            if "time_note" in e
        ]
        assert any("session" in e["time_note"] for e in task_entries)


class TestChronosBackwardCompat:
    """Existing deadline_at_risk behavior unchanged."""

    async def test_deadline_at_risk_still_works(self):
        config = EnergyConfig.for_level(EnergyLevel.medium)
        # total_hours=18 > max_daily(5)*3=15
        tasks = [
            {"title": f"Big {i}", "estimate_h": 6}
            for i in range(3)
        ]
        ctx = SharedContext(
            goal="Test",
            tasks=tasks,
            energy_config=config,
        )
        agent = ChronosAgent()
        await agent.run(ctx)
        assert ctx.get_signal("deadline_at_risk") is True

    async def test_default_profile_produces_schedule(self):
        ctx = _make_context()
        agent = ChronosAgent()
        schedule = await agent.run(ctx)
        assert len(schedule) > 0
        assert schedule[0].get("start") is not None
