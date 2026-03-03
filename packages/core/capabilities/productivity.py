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


@register_capability(
    name="check_schedule_conflicts",
    description="Check for scheduling conflicts against calendar events",
    category="productivity",
    requires_llm=False,
)
async def check_schedule_conflicts(
    tasks: list[dict[str, Any]], provider_name: str = "stub"
) -> list[dict[str, Any]]:
    """Check task schedule against calendar for conflicts.

    Parameters
    ----------
    tasks : list[dict[str, Any]]
        Scheduled tasks with start/end times.
    provider_name : str
        Calendar provider to use.

    Returns
    -------
    list[dict[str, Any]]
        List of detected conflict dicts (empty if no conflicts).
    """
    from ..integrations.calendar_provider import get_calendar_provider
    from datetime import datetime, timedelta

    provider = get_calendar_provider(provider_name)

    now = datetime.now()
    tomorrow = now + timedelta(days=1)

    try:
        events = await provider.get_events(now, tomorrow)
    except NotImplementedError:
        return []
    except Exception:
        return []

    # simple overlap detection
    conflicts: list[dict[str, Any]] = []
    for task in tasks:
        task_start = task.get("start", "")
        task_end = task.get("end", "")
        task_title = task.get("task", {})
        if isinstance(task_title, dict):
            task_title = task_title.get("title", "")

        for evt in events:
            evt_start_str = evt.start.strftime("%H:%M")
            evt_end_str = evt.end.strftime("%H:%M")
            if task_start < evt_end_str and task_end > evt_start_str:
                conflicts.append({
                    "task": task_title,
                    "task_time": f"{task_start}-{task_end}",
                    "conflict_with": evt.title,
                    "event_time": f"{evt_start_str}-{evt_end_str}",
                })

    return conflicts


@register_capability(
    name="get_estimate_insights",
    description="Get estimate accuracy insights from historical task timing data",
    category="productivity",
    requires_llm=False,
)
async def get_estimate_insights(
    user_id: str = "default", category: str | None = None
) -> dict[str, Any]:
    """Return estimate bias data for a user.

    Parameters
    ----------
    user_id : str
        The user to query.
    category : str or None
        Optional task category filter.

    Returns
    -------
    dict[str, Any]
        Estimate bias data including correction factor.
    """
    from ..estimate_learning import get_estimate_bias

    bias = await get_estimate_bias(user_id=user_id, category=category)
    return bias.model_dump()
