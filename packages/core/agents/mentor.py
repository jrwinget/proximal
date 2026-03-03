from __future__ import annotations

from typing import Any

from .base import BaseAgent
from .registry import register_agent


@register_agent("mentor")
class MentorAgent(BaseAgent):
    """Provide motivational coaching snippets."""

    name = "mentor"

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "MentorAgent()"

    async def run(self, context) -> Any:
        """Provide encouragement adapted to signals."""
        goal = context.goal
        overwhelm = context.get_signal("overwhelm_detected", False)

        if overwhelm:
            return (
                f"I see this feels like a lot right now. Let's just focus on "
                f"the very next small step for '{goal}'. You've got this."
            )
        return self.motivate(goal)

    def can_contribute(self, context) -> bool:
        return True

    def motivate(self, goal: str) -> str:
        """Return a short encouragement for the goal."""
        from ..capabilities.wellness import motivate

        return motivate(goal)
