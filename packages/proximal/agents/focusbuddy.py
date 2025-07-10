from __future__ import annotations
from typing import List, Dict
from . import BaseAgent, register_agent


@register_agent("focusbuddy")
class FocusBuddyAgent(BaseAgent):
    """Create short focus sessions for each task."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "FocusBuddyAgent()"

    def create_sessions(self, tasks: List[Dict]) -> List[Dict]:
        """Return simple 25-minute sessions for each task."""
        return [{"task": t.get("title", ""), "duration_min": 25} for t in tasks]
