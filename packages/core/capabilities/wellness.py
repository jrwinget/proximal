"""Wellness capabilities — deterministic well-being and motivation tools."""

from __future__ import annotations

from typing import Any

from .registry import register_capability


@register_capability(
    name="add_wellness_nudges",
    description="Insert well-being break reminders into task lists",
    category="wellness",
    requires_llm=False,
)
def add_wellness_nudges(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return tasks with periodic break reminders inserted every 4 items.

    Parameters
    ----------
    tasks : list[dict[str, Any]]
        List of task dicts.

    Returns
    -------
    list[dict[str, Any]]
        Original tasks interleaved with nudge entries.
    """
    output: list[dict[str, Any]] = []
    for idx, task in enumerate(tasks, start=1):
        output.append(task)
        if idx % 4 == 0:
            output.append({"title": "Take a short break", "type": "nudge"})
    return output


@register_capability(
    name="check_wellness",
    description="Check wellness patterns and return cross-session insights",
    category="wellness",
    requires_llm=False,
)
async def check_wellness(user_id: str = "default") -> list[dict[str, Any]]:
    """Run all wellness rules against recent session summaries.

    Parameters
    ----------
    user_id : str
        The user to check wellness for.

    Returns
    -------
    list[dict[str, Any]]
        List of wellness insight dicts.
    """
    from ..wellness_memory import get_session_summaries
    from ..wellness_rules import run_all_rules

    summaries = await get_session_summaries(user_id=user_id)
    insights = run_all_rules(summaries)
    return [i.model_dump() for i in insights]


@register_capability(
    name="get_wellness_summary",
    description="Get a summary of recent wellness session data",
    category="wellness",
    requires_llm=False,
)
async def get_wellness_summary(
    user_id: str = "default", limit: int = 10
) -> list[dict[str, Any]]:
    """Return recent session summaries for wellness review.

    Parameters
    ----------
    user_id : str
        The user to get summaries for.
    limit : int
        Maximum number of sessions to return.

    Returns
    -------
    list[dict[str, Any]]
        List of session summary dicts.
    """
    from ..wellness_memory import get_session_summaries

    summaries = await get_session_summaries(user_id=user_id, limit=limit)
    return [s.model_dump() for s in summaries]


@register_capability(
    name="motivate",
    description="Provide a short motivational encouragement for a goal",
    category="wellness",
    requires_llm=False,
)
def motivate(goal: str) -> str:
    """Return a short encouragement for the given goal.

    Parameters
    ----------
    goal : str
        The user's goal description.

    Returns
    -------
    str
        Motivational message.
    """
    return f"You can achieve '{goal}' if you tackle it step by step!"
