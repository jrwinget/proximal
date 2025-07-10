from __future__ import annotations
from typing import List, Dict
from . import BaseAgent, register_agent


@register_agent("focusbuddy")
class FocusBuddyAgent(BaseAgent):
    """Generate basic Pomodoro-style focus sessions."""

    def __init__(self) -> None:  # pragma: no cover
        pass

    def __repr__(self) -> str:  # pragma: no cover
        return "FocusBuddyAgent()"

    def create_sessions(self, tasks: List[Dict]) -> List[Dict]:
        """Break each task into two 25-minute focus sessions."""
        sessions: List[Dict] = []
        for task in tasks:
            for i in range(2):
                sessions.append(
                    {
                        "task": task.get("title", ""),
                        "session": i + 1,
                        "duration_min": 25,
                    }
                )
        return sessions
