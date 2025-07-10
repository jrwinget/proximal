from __future__ import annotations
from typing import List, Dict
from . import BaseAgent, register_agent


@register_agent("scribe")
class ScribeAgent(BaseAgent):
    """Simple note capturing agent."""

    def __init__(self) -> None:  # pragma: no cover
        pass

    def __repr__(self) -> str:  # pragma: no cover
        return "ScribeAgent()"

    def record(self, goal: str, tasks: List[Dict]) -> str:
        """Return a short note summary."""
        return f"Recorded {len(tasks)} tasks for '{goal}'."
