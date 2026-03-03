import pytest

from packages.core.models import (
    EnergyLevel,
    EnergyConfig,
    Task,
    Priority,
)
from packages.core.energy import apply_energy_adjustments, get_energy_prompt_context


# ---------------------------------------------------------------------------
# EnergyLevel enum
# ---------------------------------------------------------------------------


class TestEnergyLevel:
    """Tests for the EnergyLevel enum."""

    def test_values(self):
        """All three energy levels should exist with correct string values."""
        assert EnergyLevel.low == "low"
        assert EnergyLevel.medium == "medium"
        assert EnergyLevel.high == "high"

    def test_is_str_enum(self):
        """EnergyLevel members should be usable as plain strings."""
        assert isinstance(EnergyLevel.low, str)
        assert f"level={EnergyLevel.high}" == "level=high"

    def test_membership(self):
        """Should have exactly three members."""
        assert len(EnergyLevel) == 3


# ---------------------------------------------------------------------------
# EnergyConfig model and factory
# ---------------------------------------------------------------------------


class TestEnergyConfig:
    """Tests for EnergyConfig model and its for_level factory."""

    def test_for_level_low(self):
        """Low energy config should favour short, simple, gentle sessions."""
        cfg = EnergyConfig.for_level(EnergyLevel.low)
        assert cfg.max_task_duration_minutes == 15
        assert cfg.break_frequency == 2
        assert cfg.session_duration_minutes == 15
        assert cfg.max_daily_hours == 2.0
        assert cfg.task_complexity == "simple"
        assert cfg.tone == "gentle"

    def test_for_level_medium(self):
        """Medium energy config should be balanced."""
        cfg = EnergyConfig.for_level(EnergyLevel.medium)
        assert cfg.max_task_duration_minutes == 45
        assert cfg.break_frequency == 4
        assert cfg.session_duration_minutes == 25
        assert cfg.max_daily_hours == 5.0
        assert cfg.task_complexity == "moderate"
        assert cfg.tone == "balanced"

    def test_for_level_high(self):
        """High energy config should allow long complex work."""
        cfg = EnergyConfig.for_level(EnergyLevel.high)
        assert cfg.max_task_duration_minutes == 120
        assert cfg.break_frequency == 6
        assert cfg.session_duration_minutes == 50
        assert cfg.max_daily_hours == 8.0
        assert cfg.task_complexity == "complex"
        assert cfg.tone == "direct"

    def test_for_level_invalid(self):
        """Should raise KeyError for invalid energy level."""
        with pytest.raises(KeyError):
            EnergyConfig.for_level("invalid")

    def test_custom_construction(self):
        """EnergyConfig should be constructible with arbitrary values."""
        cfg = EnergyConfig(
            max_task_duration_minutes=30,
            break_frequency=3,
            session_duration_minutes=20,
            max_daily_hours=4.0,
            task_complexity="moderate",
            tone="warm",
        )
        assert cfg.max_task_duration_minutes == 30
        assert cfg.tone == "warm"


# ---------------------------------------------------------------------------
# apply_energy_adjustments
# ---------------------------------------------------------------------------


def _make_tasks(specs: list[tuple[str, int, str]]) -> list[Task]:
    """Helper: create Task objects from (title, hours, priority) tuples."""
    priority_map = {"P0": Priority.critical, "P1": Priority.high, "P2": Priority.medium, "P3": Priority.low}
    return [
        Task(title=t, detail=f"Detail for {t}", priority=priority_map[p], estimate_h=h)
        for t, h, p in specs
    ]


class TestApplyEnergyAdjustments:
    """Tests for the apply_energy_adjustments pure function."""

    def test_caps_task_durations(self):
        """Tasks exceeding max_task_duration_minutes should be capped."""
        tasks = _make_tasks([("Big task", 4, "P2")])  # 4h = 240 min
        cfg = EnergyConfig.for_level(EnergyLevel.low)  # max 15 min

        result = apply_energy_adjustments(tasks, cfg)
        non_break = [t for t in result if not t.get("is_break", False)]
        for t in non_break:
            assert t["estimate_minutes"] <= cfg.max_task_duration_minutes

    def test_inserts_breaks(self):
        """Breaks should be inserted according to break_frequency."""
        tasks = _make_tasks([
            ("Task 1", 1, "P2"),
            ("Task 2", 1, "P2"),
            ("Task 3", 1, "P2"),
            ("Task 4", 1, "P2"),
            ("Task 5", 1, "P2"),
        ])
        cfg = EnergyConfig.for_level(EnergyLevel.low)  # break every 2 tasks

        result = apply_energy_adjustments(tasks, cfg)
        breaks = [t for t in result if t.get("is_break", False)]
        assert len(breaks) >= 1

    def test_limits_daily_hours(self):
        """Total scheduled work should not exceed max_daily_hours."""
        tasks = _make_tasks([
            ("Task A", 3, "P2"),
            ("Task B", 3, "P2"),
            ("Task C", 3, "P2"),
        ])
        cfg = EnergyConfig.for_level(EnergyLevel.low)  # max 2h per day

        result = apply_energy_adjustments(tasks, cfg)
        work_items = [t for t in result if not t.get("is_break", False)]
        total_minutes = sum(t["estimate_minutes"] for t in work_items)
        assert total_minutes <= cfg.max_daily_hours * 60

    def test_low_energy_reorders_by_difficulty(self):
        """Low energy should place simpler/lower-priority tasks first."""
        tasks = _make_tasks([
            ("Critical task", 1, "P0"),
            ("Easy task", 1, "P3"),
            ("Medium task", 1, "P2"),
        ])
        cfg = EnergyConfig.for_level(EnergyLevel.low)

        result = apply_energy_adjustments(tasks, cfg)
        work_items = [t for t in result if not t.get("is_break", False)]
        if len(work_items) >= 2:
            # lower priority (P3) should come before critical (P0) at low energy
            titles = [t["title"] for t in work_items]
            assert titles.index("Easy task") < titles.index("Critical task")

    def test_high_energy_preserves_priority_order(self):
        """High energy should keep tasks in priority order (P0 first)."""
        tasks = _make_tasks([
            ("Easy task", 1, "P3"),
            ("Critical task", 1, "P0"),
            ("Medium task", 1, "P2"),
        ])
        cfg = EnergyConfig.for_level(EnergyLevel.high)

        result = apply_energy_adjustments(tasks, cfg)
        work_items = [t for t in result if not t.get("is_break", False)]
        if len(work_items) >= 2:
            titles = [t["title"] for t in work_items]
            assert titles.index("Critical task") < titles.index("Easy task")

    def test_empty_task_list(self):
        """Should handle an empty task list gracefully."""
        cfg = EnergyConfig.for_level(EnergyLevel.medium)
        result = apply_energy_adjustments([], cfg)
        assert result == []

    def test_returns_list_of_dicts(self):
        """Each item in the result should be a dict with expected keys."""
        tasks = _make_tasks([("Test", 1, "P2")])
        cfg = EnergyConfig.for_level(EnergyLevel.medium)
        result = apply_energy_adjustments(tasks, cfg)
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)
            assert "title" in item
            assert "estimate_minutes" in item


# ---------------------------------------------------------------------------
# get_energy_prompt_context
# ---------------------------------------------------------------------------


class TestGetEnergyPromptContext:
    """Tests for the get_energy_prompt_context function."""

    def test_returns_string(self):
        """Should return a non-empty string."""
        cfg = EnergyConfig.for_level(EnergyLevel.medium)
        ctx = get_energy_prompt_context(cfg)
        assert isinstance(ctx, str)
        assert len(ctx) > 0

    def test_contains_tone(self):
        """Prompt context should mention the configured tone."""
        cfg = EnergyConfig.for_level(EnergyLevel.low)
        ctx = get_energy_prompt_context(cfg)
        assert "gentle" in ctx.lower()

    def test_contains_complexity(self):
        """Prompt context should mention task complexity."""
        cfg = EnergyConfig.for_level(EnergyLevel.high)
        ctx = get_energy_prompt_context(cfg)
        assert "complex" in ctx.lower()

    def test_contains_session_duration(self):
        """Prompt context should reference session duration."""
        cfg = EnergyConfig.for_level(EnergyLevel.medium)
        ctx = get_energy_prompt_context(cfg)
        assert "25" in ctx  # 25 minute sessions

    def test_contains_max_daily_hours(self):
        """Prompt context should reference daily hour cap."""
        cfg = EnergyConfig.for_level(EnergyLevel.low)
        ctx = get_energy_prompt_context(cfg)
        assert "2.0" in ctx or "2 " in ctx

    def test_all_levels_produce_distinct_contexts(self):
        """Each energy level should produce a different prompt context."""
        contexts = set()
        for level in EnergyLevel:
            cfg = EnergyConfig.for_level(level)
            contexts.add(get_energy_prompt_context(cfg))
        assert len(contexts) == 3
