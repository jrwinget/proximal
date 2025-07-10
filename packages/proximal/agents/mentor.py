from __future__ import annotations
from . import BaseAgent, register_agent


@register_agent("mentor")
class MentorAgent(BaseAgent):
    """Provide short motivational coaching."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover
        return "MentorAgent()"

    def coach(self, goal: str) -> str:
        """Return a basic encouragement message."""
        return f"Stay focused on your goal: {goal}! You've got this."
