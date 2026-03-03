"""Plain async pipeline replacing LangGraph state machines."""

from __future__ import annotations

from typing import Any, Optional

from packages.core.agents import (
    clarify_llm,
    integrate_clarifications_llm,
    plan_llm,
    prioritize_llm,
    estimate_llm,
    package_llm,
)


async def run_direct_pipeline(goal: str, **kwargs: Any) -> dict:
    """Run the direct (non-interactive) planning pipeline.

    Parameters
    ----------
    goal : str
        The user's project goal.
    **kwargs : Any
        Additional state passed through the pipeline.

    Returns
    -------
    dict
        Pipeline state including 'sprints' key with the final plan.
    """
    state: dict[str, Any] = {"goal": goal, **kwargs}
    state = await plan_llm(state)
    state = await prioritize_llm(state)
    state = await estimate_llm(state)
    state = await package_llm(state)
    return state


async def run_interactive_pipeline(
    goal: str,
    session_id: Optional[str] = None,
    **kwargs: Any,
) -> dict:
    """Run the interactive pipeline with clarification support.

    Parameters
    ----------
    goal : str
        The user's project goal.
    session_id : str, optional
        Session identifier for conversation tracking.
    **kwargs : Any
        Additional state passed through the pipeline.

    Returns
    -------
    dict
        Pipeline state. If clarification is needed, contains
        'needs_clarification' and 'clarification_questions'. Otherwise
        contains 'sprints' with the final plan.
    """
    state: dict[str, Any] = {"goal": goal, "session_id": session_id, **kwargs}
    state = await clarify_llm(state)
    if state.get("needs_clarification"):
        return state  # return to user for answers
    state = await integrate_clarifications_llm(state)
    state = await plan_llm(state)
    state = await prioritize_llm(state)
    state = await estimate_llm(state)
    state = await package_llm(state)
    return state
