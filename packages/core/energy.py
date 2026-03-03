"""Energy-aware planning utilities.

Pure functions for adapting task lists to the user's current energy level.
No LLM calls, no side effects.
"""

from __future__ import annotations

from typing import Any

from packages.core.models import EnergyConfig, Priority, Task


# priority sort keys — lower number = harder/more important
_PRIORITY_SORT = {
    Priority.critical: 0,
    Priority.high: 1,
    Priority.medium: 2,
    Priority.low: 3,
}


def apply_energy_adjustments(
    tasks: list[Task],
    energy_config: EnergyConfig,
) -> list[dict[str, Any]]:
    """Adjust a task list based on the user's energy configuration.

    Applies four transformations in order:
    1. Reorder — low energy places easier tasks first; otherwise priority order.
    2. Cap durations — no task exceeds ``max_task_duration_minutes``.
    3. Insert breaks — a break every ``break_frequency`` tasks.
    4. Limit daily hours — total work time stays within ``max_daily_hours``.

    Parameters
    ----------
    tasks : list[Task]
        The raw task list (pydantic Task models).
    energy_config : EnergyConfig
        Configuration controlling the adjustments.

    Returns
    -------
    list[dict[str, Any]]
        Adjusted schedule items. Work items have at minimum
        ``title``, ``estimate_minutes``, ``priority``, and ``is_break=False``.
        Break items have ``title="Break"``, ``is_break=True``, and
        ``estimate_minutes`` equal to the session duration.
    """
    if not tasks:
        return []

    # step 1: reorder based on energy level
    sorted_tasks = _reorder_tasks(tasks, energy_config)

    # step 2: convert to dicts and cap durations
    items: list[dict[str, Any]] = []
    for task in sorted_tasks:
        raw_minutes = task.estimate_h * 60
        capped_minutes = min(raw_minutes, energy_config.max_task_duration_minutes)
        items.append(
            {
                "title": task.title,
                "detail": task.detail,
                "priority": task.priority.value,
                "estimate_minutes": capped_minutes,
                "is_break": False,
            }
        )

    # step 3: insert breaks
    items = _insert_breaks(items, energy_config)

    # step 4: limit daily hours
    items = _limit_daily_hours(items, energy_config)

    return items


def _reorder_tasks(tasks: list[Task], cfg: EnergyConfig) -> list[Task]:
    """Reorder tasks based on energy level.

    Low energy → easiest first (reverse priority).
    Medium/high energy → hardest/most important first (priority order).
    """
    if cfg.tone == "gentle":
        # low energy: easiest first (highest P-number first)
        return sorted(tasks, key=lambda t: -_PRIORITY_SORT.get(t.priority, 2))
    else:
        # medium/high: most important first (lowest P-number first)
        return sorted(tasks, key=lambda t: _PRIORITY_SORT.get(t.priority, 2))


def _insert_breaks(
    items: list[dict[str, Any]],
    cfg: EnergyConfig,
) -> list[dict[str, Any]]:
    """Insert break items after every ``break_frequency`` work tasks."""
    if cfg.break_frequency <= 0:
        return items

    result: list[dict[str, Any]] = []
    work_count = 0

    for item in items:
        if item.get("is_break"):
            result.append(item)
            continue

        result.append(item)
        work_count += 1

        if work_count % cfg.break_frequency == 0:
            result.append(
                {
                    "title": "Break",
                    "estimate_minutes": cfg.session_duration_minutes,
                    "is_break": True,
                }
            )

    return result


def _limit_daily_hours(
    items: list[dict[str, Any]],
    cfg: EnergyConfig,
) -> list[dict[str, Any]]:
    """Trim the schedule so total work time does not exceed max_daily_hours."""
    max_minutes = cfg.max_daily_hours * 60
    result: list[dict[str, Any]] = []
    work_minutes = 0

    for item in items:
        if item.get("is_break"):
            # include breaks only if there is still work budget
            if work_minutes < max_minutes:
                result.append(item)
            continue

        if work_minutes + item["estimate_minutes"] > max_minutes:
            # remaining budget
            remaining = max_minutes - work_minutes
            if remaining > 0:
                trimmed = {**item, "estimate_minutes": int(remaining)}
                result.append(trimmed)
                work_minutes += remaining
            break

        result.append(item)
        work_minutes += item["estimate_minutes"]

    return result


def get_energy_prompt_context(energy_config: EnergyConfig) -> str:
    """Generate an LLM prompt fragment describing energy-aware constraints.

    Parameters
    ----------
    energy_config : EnergyConfig
        The active energy configuration.

    Returns
    -------
    str
        A multi-line prompt string that can be injected into an LLM system
        message to guide energy-aware planning.
    """
    return (
        f"The user's current energy level calls for a {energy_config.tone} tone. "
        f"Keep tasks at {energy_config.task_complexity} complexity or below. "
        f"Each task should be at most {energy_config.max_task_duration_minutes} minutes. "
        f"Use {energy_config.session_duration_minutes}-minute focus sessions "
        f"with a break every {energy_config.break_frequency} tasks. "
        f"Do not exceed {energy_config.max_daily_hours} hours of work per day."
    )
