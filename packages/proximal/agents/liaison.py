from __future__ import annotations
from . import BaseAgent, register_agent


@register_agent("liaison")
class LiaisonAgent(BaseAgent):
    """Draft simple communication messages."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "LiaisonAgent()"

    def draft_message(self, goal: str) -> str:
        """Return a short status update about the goal."""
        return f"Status update: planning work on '{goal}'."
