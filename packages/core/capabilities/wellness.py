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
