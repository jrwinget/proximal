"""Tests for wellness pattern detection rules (WP3)."""

from datetime import datetime, timedelta, timezone

from packages.core.models import (
    EscalationLevel,
    WellnessSessionSummary,
)
from packages.core.wellness_rules import (
    detect_consecutive_no_break_sessions,
    detect_declining_break_compliance,
    detect_extended_work_without_break,
    detect_late_session_pattern,
    run_all_rules,
)


def _make_summary(
    session_id: str = "s1",
    tasks_completed: int = 3,
    breaks_taken: int = 1,
    breaks_skipped: int = 0,
    duration_hours: float = 1.5,
    was_late_session: bool = False,
    started_at: datetime | None = None,
) -> WellnessSessionSummary:
    """Helper to build a session summary."""
    return WellnessSessionSummary(
        session_id=session_id,
        user_id="test",
        started_at=started_at or datetime.now(timezone.utc),
        ended_at=(started_at or datetime.now(timezone.utc))
        + timedelta(hours=duration_hours),
        tasks_completed=tasks_completed,
        breaks_taken=breaks_taken,
        breaks_skipped=breaks_skipped,
        duration_hours=duration_hours,
        was_late_session=was_late_session,
    )


class TestConsecutiveNoBreaks:
    def test_triggers_at_threshold(self):
        summaries = [
            _make_summary(session_id=f"s{i}", breaks_taken=0, tasks_completed=2)
            for i in range(3)
        ]
        result = detect_consecutive_no_break_sessions(summaries, threshold=3)
        assert result is not None
        assert result.rule_name == "consecutive_no_breaks"
        assert result.severity == EscalationLevel.firm_reminder

    def test_does_not_trigger_below_threshold(self):
        summaries = [
            _make_summary(session_id="s1", breaks_taken=0, tasks_completed=2),
            _make_summary(session_id="s2", breaks_taken=0, tasks_completed=2),
        ]
        result = detect_consecutive_no_break_sessions(summaries, threshold=3)
        assert result is None

    def test_break_in_streak_resets(self):
        summaries = [
            _make_summary(session_id="s1", breaks_taken=0, tasks_completed=2),
            _make_summary(session_id="s2", breaks_taken=0, tasks_completed=2),
            _make_summary(session_id="s3", breaks_taken=1, tasks_completed=2),
            _make_summary(session_id="s4", breaks_taken=0, tasks_completed=2),
        ]
        result = detect_consecutive_no_break_sessions(summaries, threshold=3)
        assert result is None

    def test_no_tasks_not_counted(self):
        """Sessions with no tasks completed should not count as no-break."""
        summaries = [
            _make_summary(session_id=f"s{i}", breaks_taken=0, tasks_completed=0)
            for i in range(3)
        ]
        result = detect_consecutive_no_break_sessions(summaries, threshold=3)
        assert result is None


class TestExtendedWork:
    def test_triggers_on_long_sessions(self):
        summaries = [
            _make_summary(session_id=f"s{i}", duration_hours=4.0) for i in range(5)
        ]
        result = detect_extended_work_without_break(
            summaries, max_hours=3.0, recurring=5
        )
        assert result is not None
        assert result.rule_name == "extended_work"

    def test_does_not_trigger_on_short_sessions(self):
        summaries = [
            _make_summary(session_id=f"s{i}", duration_hours=1.0) for i in range(5)
        ]
        result = detect_extended_work_without_break(
            summaries, max_hours=3.0, recurring=5
        )
        assert result is None

    def test_single_long_session_not_enough(self):
        summaries = [
            _make_summary(session_id="s1", duration_hours=4.0),
            _make_summary(session_id="s2", duration_hours=1.0),
            _make_summary(session_id="s3", duration_hours=1.0),
        ]
        result = detect_extended_work_without_break(
            summaries, max_hours=3.0, recurring=5
        )
        assert result is None


class TestDecliningCompliance:
    def test_triggers_on_decline(self):
        # older sessions have good compliance, newer have poor
        summaries = [
            # newer (poor compliance)
            _make_summary(session_id="s1", breaks_taken=0, breaks_skipped=3),
            _make_summary(session_id="s2", breaks_taken=0, breaks_skipped=3),
            _make_summary(session_id="s3", breaks_taken=1, breaks_skipped=2),
            # older (good compliance)
            _make_summary(session_id="s4", breaks_taken=3, breaks_skipped=0),
            _make_summary(session_id="s5", breaks_taken=3, breaks_skipped=0),
            _make_summary(session_id="s6", breaks_taken=3, breaks_skipped=0),
            _make_summary(session_id="s7", breaks_taken=3, breaks_skipped=0),
        ]
        result = detect_declining_break_compliance(summaries, window=7)
        assert result is not None
        assert result.rule_name == "declining_break_compliance"

    def test_no_trigger_on_stable(self):
        summaries = [
            _make_summary(session_id=f"s{i}", breaks_taken=2, breaks_skipped=1)
            for i in range(7)
        ]
        result = detect_declining_break_compliance(summaries, window=7)
        assert result is None

    def test_too_few_sessions(self):
        summaries = [_make_summary(session_id="s1")]
        result = detect_declining_break_compliance(summaries, window=7)
        assert result is None


class TestLateSessionPattern:
    def test_triggers_on_late_sessions(self):
        summaries = [
            _make_summary(session_id=f"s{i}", was_late_session=True) for i in range(4)
        ]
        result = detect_late_session_pattern(summaries, threshold=3)
        assert result is not None
        assert result.rule_name == "late_session_pattern"

    def test_does_not_trigger_below_threshold(self):
        summaries = [
            _make_summary(session_id="s1", was_late_session=True),
            _make_summary(session_id="s2", was_late_session=False),
            _make_summary(session_id="s3", was_late_session=False),
        ]
        result = detect_late_session_pattern(summaries, threshold=3)
        assert result is None


class TestRunAllRules:
    def test_returns_multiple_insights(self):
        summaries = [
            _make_summary(
                session_id=f"s{i}",
                breaks_taken=0,
                tasks_completed=2,
                duration_hours=4.0,
                was_late_session=True,
            )
            for i in range(5)
        ]
        insights = run_all_rules(summaries)
        assert len(insights) >= 2

    def test_returns_empty_on_healthy(self):
        summaries = [
            _make_summary(
                session_id=f"s{i}",
                breaks_taken=2,
                tasks_completed=3,
                duration_hours=1.5,
                was_late_session=False,
            )
            for i in range(5)
        ]
        insights = run_all_rules(summaries)
        assert len(insights) == 0
