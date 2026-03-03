from __future__ import annotations

from typing import Any
from .registry import register_agent


@register_agent("focusbuddy")
class FocusBuddyAgent:
    """Create short focus sessions for each task."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "FocusBuddyAgent()"

    def create_sessions(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return simple 25-minute sessions for each task."""
        from ..capabilities.productivity import create_focus_sessions

        return create_focus_sessions(tasks)
