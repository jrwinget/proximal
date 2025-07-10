from __future__ import annotations
from typing import List, Dict
from . import BaseAgent, register_agent


@register_agent("guardian")
class GuardianAgent(BaseAgent):
    """Inject wellness reminders into a task list."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover
        return "GuardianAgent()"

    def suggest_breaks(self, tasks: List[Dict]) -> List[str]:
        """Return basic wellness reminders after every 2 tasks."""
        reminders: List[str] = []
        for i in range(0, len(tasks), 2):
            reminders.append(f"Take a short break after task {i + 1}")
        return reminders
