from __future__ import annotations
from . import BaseAgent, register_agent


@register_agent("liaison")
class LiaisonAgent(BaseAgent):
    """Create simple communication drafts."""

    def __init__(self) -> None:  # pragma: no cover
        pass

    def __repr__(self) -> str:  # pragma: no cover
        return "LiaisonAgent()"

    def compose_message(self, goal: str) -> str:
        """Return a basic status email draft."""
        return f"Hello team, I'm planning to {goal}. More details soon."
