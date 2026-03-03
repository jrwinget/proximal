"""Productivity capabilities — deterministic scheduling and focus tools."""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any

from .registry import register_capability


@register_capability(
    name="create_schedule",
    description="Create a deterministic daily schedule with hourly blocks and breaks",
    category="productivity",
    requires_llm=False,
)
def create_schedule(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Assign tasks into hourly blocks starting at 09:00 with breaks every 3 tasks.

    Parameters
    ----------
    tasks : list[dict[str, Any]]
        List of task dicts, each expected to have at least a ``"title"`` key.

    Returns
    -------
    list[dict[str, Any]]
        Schedule entries with ``task``, ``start``, and ``end`` keys.
    """
    schedule: list[dict[str, Any]] = []
    current = datetime.combine(datetime.today(), datetime.min.time()).replace(
        hour=9, minute=0
    )

    for index, task in enumerate(tasks, start=1):
        end = current + timedelta(hours=1)
        schedule.append(
            {
                "task": task,
                "start": current.strftime("%H:%M"),
                "end": end.strftime("%H:%M"),
            }
        )
        current = end

        if index % 3 == 0:
            break_end = current + timedelta(minutes=5)
            schedule.append(
                {
                    "task": {"title": "Break"},
                    "start": current.strftime("%H:%M"),
                    "end": break_end.strftime("%H:%M"),
                }
            )
            current = break_end

    # trigger automatisch workflow if configured
    if os.getenv("AUTOMATISCH_URL"):
        from ..integrations.automatisch import trigger_workflow

        trigger_workflow("schedule", {"schedule": schedule})

    return schedule


@register_capability(
    name="create_focus_sessions",
    description="Create 25-minute Pomodoro focus sessions for each task",
    category="productivity",
    requires_llm=False,
)
def create_focus_sessions(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return simple 25-minute focus sessions for each task.

    Parameters
    ----------
    tasks : list[dict[str, Any]]
        List of task dicts, each expected to have a ``"title"`` key.

    Returns
    -------
    list[dict[str, Any]]
        Sessions with ``task`` (title string) and ``duration_min`` keys.
    """
    return [{"task": t.get("title", ""), "duration_min": 25} for t in tasks]
