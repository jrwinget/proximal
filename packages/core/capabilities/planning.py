"""Planning capabilities — LLM-powered planning functions extracted from PlannerAgent."""

from __future__ import annotations

from typing import Any

from ..agents.planner import PlannerAgent
from .registry import register_capability

# shared lazy singleton
_planner: PlannerAgent | None = None


def _get_planner() -> PlannerAgent:
    """Return a cached PlannerAgent instance."""
    global _planner
    if _planner is None:
        _planner = PlannerAgent()
    return _planner


@register_capability(
    name="clarify",
    description="Check if a goal needs clarification and generate targeted questions",
    category="planning",
    requires_llm=True,
)
async def clarify(state: dict[str, Any]) -> dict[str, Any]:
    """Determine whether a goal needs clarification.

    Parameters
    ----------
    state : dict[str, Any]
        Planning state dict containing at least ``"goal"``.

    Returns
    -------
    dict[str, Any]
        Dict with ``"needs_clarification"`` and ``"clarification_questions"`` keys.
    """
    return await _get_planner().clarify_llm(state)


@register_capability(
    name="plan",
    description="Transform a goal into a detailed task breakdown",
    category="planning",
    requires_llm=True,
)
async def plan(state: dict[str, Any]) -> dict[str, Any]:
    """Generate tasks from a goal.

    Parameters
    ----------
    state : dict[str, Any]
        Planning state dict containing at least ``"goal"``.

    Returns
    -------
    dict[str, Any]
        Dict with ``"tasks"`` key containing a list of Task objects.
    """
    return await _get_planner().plan_llm(state)


@register_capability(
    name="prioritize",
    description="Assign priority levels to tasks",
    category="planning",
    requires_llm=True,
)
async def prioritize(state: dict[str, Any]) -> dict[str, Any]:
    """Assign priorities to tasks.

    Parameters
    ----------
    state : dict[str, Any]
        Planning state dict containing ``"tasks"``.

    Returns
    -------
    dict[str, Any]
        Dict with updated ``"tasks"`` containing priorities.
    """
    return await _get_planner().prioritize_llm(state)


@register_capability(
    name="estimate",
    description="Add time estimates to tasks",
    category="planning",
    requires_llm=True,
)
async def estimate(state: dict[str, Any]) -> dict[str, Any]:
    """Add hour estimates to tasks.

    Parameters
    ----------
    state : dict[str, Any]
        Planning state dict containing ``"tasks"``.

    Returns
    -------
    dict[str, Any]
        Dict with updated ``"tasks"`` containing ``estimate_h`` values.
    """
    return await _get_planner().estimate_llm(state)


@register_capability(
    name="package_tasks",
    description="Group tasks into sprints",
    category="planning",
    requires_llm=True,
)
async def package_tasks(state: dict[str, Any]) -> dict[str, Any]:
    """Group tasks into time-boxed sprints.

    Parameters
    ----------
    state : dict[str, Any]
        Planning state dict containing ``"tasks"``.

    Returns
    -------
    dict[str, Any]
        Dict with ``"sprints"`` key.
    """
    return await _get_planner().package_llm(state)
