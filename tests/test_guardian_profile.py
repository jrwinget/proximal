"""Tests for Phase 1.3: Guardian uses low_energy_days for proactive wellness."""

from __future__ import annotations

from datetime import datetime

from packages.core.agents.guardian import GuardianAgent
from packages.core.collaboration.context import SharedContext
from packages.core.models import UserProfile


def _make_context(tasks=None, **profile_kwargs):
    profile = UserProfile(**profile_kwargs)
    return SharedContext(
        goal="Test",
        tasks=tasks or [{"title": f"T{i}"} for i in range(3)],
        user_profile=profile,
    )


# use a known monday for testing
_MONDAY = datetime(2026, 3, 2, 10, 0)  # 2026-03-02 is a Monday
_TUESDAY = datetime(2026, 3, 3, 10, 0)


class TestGuardianLowEnergyDays:
    """low_energy_days triggers proactive low-energy mode."""

    async def test_low_energy_day_sets_signal(self):
        ctx = _make_context(low_energy_days=["Monday"])
        agent = GuardianAgent()
        await agent.run(ctx, _now=_MONDAY)
        assert ctx.get_signal("low_energy_mode") is True

    async def test_normal_day_no_preemptive_signal(self):
        ctx = _make_context(low_energy_days=["Monday"])
        agent = GuardianAgent()
        # tuesday is not a low-energy day
        await agent.run(ctx, _now=_TUESDAY)
        assert ctx.get_signal("low_energy_mode") is None

    async def test_empty_low_energy_days(self):
        ctx = _make_context(low_energy_days=[])
        agent = GuardianAgent()
        await agent.run(ctx, _now=_MONDAY)
        assert ctx.get_signal("low_energy_mode") is None


class TestGuardianReducedThreshold:
    """Overwhelm threshold is reduced ~30% on low-energy days."""

    async def test_reduced_threshold_on_low_energy_day(self):
        # threshold=5, effective=3 on low day; 4 tasks triggers overwhelm
        ctx = _make_context(
            tasks=[{"title": f"T{i}"} for i in range(4)],
            overwhelm_threshold=5,
            low_energy_days=["Monday"],
        )
        agent = GuardianAgent()
        await agent.run(ctx, _now=_MONDAY)
        assert ctx.get_signal("overwhelm_detected") is True

    async def test_normal_threshold_on_normal_day(self):
        # same 4 tasks but threshold=5 on a normal day → no overwhelm
        ctx = _make_context(
            tasks=[{"title": f"T{i}"} for i in range(4)],
            overwhelm_threshold=5,
            low_energy_days=["Monday"],
        )
        agent = GuardianAgent()
        await agent.run(ctx, _now=_TUESDAY)
        assert ctx.get_signal("overwhelm_detected") is None


class TestGuardianOverwhelmBackwardCompat:
    """Existing overwhelm detection still works on normal days."""

    async def test_overwhelm_still_works_normally(self):
        ctx = _make_context(
            tasks=[{"title": f"T{i}"} for i in range(6)],
            overwhelm_threshold=5,
        )
        agent = GuardianAgent()
        await agent.run(ctx, _now=_TUESDAY)
        assert ctx.get_signal("overwhelm_detected") is True

    async def test_no_overwhelm_within_threshold(self):
        ctx = _make_context(
            tasks=[{"title": f"T{i}"} for i in range(3)],
            overwhelm_threshold=5,
        )
        agent = GuardianAgent()
        await agent.run(ctx, _now=_TUESDAY)
        assert ctx.get_signal("overwhelm_detected") is None


class TestGuardianHelpers:
    """Direct tests for _is_low_energy_day helper."""

    def test_is_low_energy_day_match(self):
        profile = UserProfile(low_energy_days=["Monday", "Friday"])
        assert (
            GuardianAgent._is_low_energy_day(
                profile,
                _now=_MONDAY,
            )
            is True
        )

    def test_is_low_energy_day_no_match(self):
        profile = UserProfile(low_energy_days=["Monday", "Friday"])
        assert (
            GuardianAgent._is_low_energy_day(
                profile,
                _now=_TUESDAY,
            )
            is False
        )

    def test_is_low_energy_day_case_insensitive(self):
        profile = UserProfile(low_energy_days=["monday"])
        assert (
            GuardianAgent._is_low_energy_day(
                profile,
                _now=_MONDAY,
            )
            is True
        )

    def test_is_low_energy_day_empty_list(self):
        profile = UserProfile(low_energy_days=[])
        assert (
            GuardianAgent._is_low_energy_day(
                profile,
                _now=_MONDAY,
            )
            is False
        )
