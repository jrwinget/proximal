"""Pure-function wellness pattern detection rules.

These rules operate on ``WellnessSessionSummary`` lists and produce
``WellnessInsight`` objects. No LLM calls — all deterministic.
"""

from __future__ import annotations

from .models import (
    EscalationLevel,
    WellnessInsight,
    WellnessSessionSummary,
)


def detect_consecutive_no_break_sessions(
    summaries: list[WellnessSessionSummary],
    threshold: int = 3,
) -> WellnessInsight | None:
    """Detect consecutive sessions where no breaks were taken.

    Parameters
    ----------
    summaries : list[WellnessSessionSummary]
        Session summaries ordered most-recent-first.
    threshold : int
        Number of consecutive no-break sessions to trigger.

    Returns
    -------
    WellnessInsight or None
        Insight if pattern detected, None otherwise.
    """
    streak = 0
    for s in summaries:
        if s.breaks_taken == 0 and s.tasks_completed > 0:
            streak += 1
        else:
            break

    if streak >= threshold:
        return WellnessInsight(
            rule_name="consecutive_no_breaks",
            severity=EscalationLevel.firm_reminder,
            message=(
                f"You've gone {streak} sessions in a row without taking a break. "
                "Regular breaks help maintain focus and prevent burnout."
            ),
            data={"streak": streak},
        )
    return None


def detect_extended_work_without_break(
    summaries: list[WellnessSessionSummary],
    max_hours: float = 3.0,
    recurring: int = 5,
) -> WellnessInsight | None:
    """Detect sessions that exceeded a safe work duration.

    Parameters
    ----------
    summaries : list[WellnessSessionSummary]
        Session summaries ordered most-recent-first.
    max_hours : float
        Maximum hours before a session is flagged.
    recurring : int
        Number of recent sessions to check.

    Returns
    -------
    WellnessInsight or None
        Insight if pattern detected.
    """
    recent = summaries[:recurring]
    long_sessions = [s for s in recent if s.duration_hours > max_hours]

    if len(long_sessions) >= 2:
        return WellnessInsight(
            rule_name="extended_work",
            severity=EscalationLevel.escalated_warning,
            message=(
                f"You've had {len(long_sessions)} sessions over {max_hours} hours "
                f"in your last {len(recent)} sessions. Long work blocks without rest "
                "increase the risk of burnout."
            ),
            data={
                "long_session_count": len(long_sessions),
                "window": len(recent),
                "max_hours": max_hours,
            },
        )
    return None


def detect_declining_break_compliance(
    summaries: list[WellnessSessionSummary],
    window: int = 7,
) -> WellnessInsight | None:
    """Detect a declining trend in break-taking behaviour.

    Compares the break compliance rate of the most recent half of sessions
    against the older half within the window.

    Parameters
    ----------
    summaries : list[WellnessSessionSummary]
        Session summaries ordered most-recent-first.
    window : int
        Number of recent sessions to analyse.

    Returns
    -------
    WellnessInsight or None
        Insight if compliance is declining.
    """
    recent = summaries[:window]
    if len(recent) < 4:
        return None

    mid = len(recent) // 2
    newer = recent[:mid]
    older = recent[mid:]

    def compliance(sessions):
        total = sum(s.breaks_taken + s.breaks_skipped for s in sessions)
        taken = sum(s.breaks_taken for s in sessions)
        return taken / total if total > 0 else 1.0

    newer_rate = compliance(newer)
    older_rate = compliance(older)

    if older_rate > 0 and newer_rate < older_rate * 0.7:
        return WellnessInsight(
            rule_name="declining_break_compliance",
            severity=EscalationLevel.gentle_nudge,
            message=(
                "Your break-taking has declined recently. "
                "Even short pauses help maintain sustained focus."
            ),
            data={
                "newer_rate": round(newer_rate, 2),
                "older_rate": round(older_rate, 2),
            },
        )
    return None


def detect_late_session_pattern(
    summaries: list[WellnessSessionSummary],
    late_hour: int = 22,
    threshold: int = 3,
) -> WellnessInsight | None:
    """Detect a pattern of working during late hours.

    Parameters
    ----------
    summaries : list[WellnessSessionSummary]
        Session summaries ordered most-recent-first.
    late_hour : int
        Hour of day (0-23) after which a session is considered late.
    threshold : int
        Number of late sessions in the window to trigger.

    Returns
    -------
    WellnessInsight or None
        Insight if pattern detected.
    """
    recent = summaries[:10]
    late_count = sum(1 for s in recent if s.was_late_session)

    if late_count >= threshold:
        return WellnessInsight(
            rule_name="late_session_pattern",
            severity=EscalationLevel.firm_reminder,
            message=(
                f"You've had {late_count} late-night sessions recently. "
                "Working late can disrupt sleep and reduce next-day productivity."
            ),
            data={"late_count": late_count, "late_hour": late_hour},
        )
    return None


def run_all_rules(
    summaries: list[WellnessSessionSummary],
) -> list[WellnessInsight]:
    """Run all wellness detection rules and return any triggered insights.

    Parameters
    ----------
    summaries : list[WellnessSessionSummary]
        Session summaries ordered most-recent-first.

    Returns
    -------
    list[WellnessInsight]
        All detected insights (may be empty).
    """
    rules = [
        detect_consecutive_no_break_sessions,
        detect_extended_work_without_break,
        detect_declining_break_compliance,
        detect_late_session_pattern,
    ]

    insights = []
    for rule in rules:
        result = rule(summaries)
        if result is not None:
            insights.append(result)
    return insights
