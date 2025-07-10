from __future__ import annotations
from typing import List, Dict
from . import PlannerAgent, register_agent


@register_agent("guardian")
class GuardianAgent(PlannerAgent):
    """Insert well-being reminders into task lists."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "GuardianAgent()"

    def add_nudges(self, tasks: List[Dict]) -> List[Dict]:
        """Return tasks with periodic break reminders."""
        output: List[Dict] = []
        for idx, task in enumerate(tasks, start=1):
            output.append(task)
            if idx % 4 == 0:
                output.append({"title": "Take a short break", "type": "nudge"})
        return output
