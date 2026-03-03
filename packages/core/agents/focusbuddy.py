from __future__ import annotations

from typing import Any

from .base import BaseAgent
from .registry import register_agent


@register_agent("focusbuddy")
class FocusBuddyAgent(BaseAgent):
    """Create short focus sessions for each task."""

    name = "focusbuddy"

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "FocusBuddyAgent()"

    async def run(self, context) -> Any:
        """Create focus sessions adapted to energy signals."""
        tasks = context.tasks or []
        energy = context.energy_config

        # adapt session duration to energy level
        sessions = []
        for t in tasks:
            sessions.append({
                "task": t.get("title", ""),
                "duration_min": energy.session_duration_minutes,
            })
        return sessions

    def can_contribute(self, context) -> bool:
        return True

    def create_sessions(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return simple 25-minute sessions for each task."""
        from ..capabilities.productivity import create_focus_sessions

        return create_focus_sessions(tasks)
