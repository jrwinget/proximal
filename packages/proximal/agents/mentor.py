from __future__ import annotations
from . import PlannerAgent, register_agent


@register_agent("mentor")
class MentorAgent(PlannerAgent):
    """Provide motivational coaching snippets."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "MentorAgent()"

    def motivate(self, goal: str) -> str:
        """Return a short encouragement for the goal."""
        return f"You can achieve '{goal}' if you tackle it step by step!"
