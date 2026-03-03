from __future__ import annotations

from .registry import register_agent


@register_agent("mentor")
class MentorAgent:
    """Provide motivational coaching snippets."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "MentorAgent()"

    def motivate(self, goal: str) -> str:
        """Return a short encouragement for the goal."""
        from ..capabilities.wellness import motivate

        return motivate(goal)
