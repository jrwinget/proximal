"""Communication capabilities — LLM-powered message drafting."""

from __future__ import annotations

from typing import Any

from ..agents.liaison import LiaisonAgent
from .registry import register_capability


@register_capability(
    name="draft_message",
    description="Draft a context-aware communication message using LLM",
    category="communication",
    requires_llm=True,
)
async def draft_message(
    goal: str,
    message_type: str = "status_update",
    audience: str = "teammate",
    tone: str | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Draft a communication message by delegating to LiaisonAgent.

    Parameters
    ----------
    goal : str
        The topic or project being communicated about.
    message_type : str, optional
        Type of message, by default ``"status_update"``.
    audience : str, optional
        Target audience, by default ``"teammate"``.
    tone : str or None, optional
        Communication tone override.
    context : dict or None, optional
        Additional context for the message.

    Returns
    -------
    dict[str, Any]
        Message dict with ``subject``, ``message``, ``tone``, etc.
    """
    agent = LiaisonAgent()
    return await agent.draft_message(
        goal=goal,
        message_type=message_type,
        audience=audience,
        tone=tone,
        context=context,
    )
