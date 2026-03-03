from __future__ import annotations

from typing import Any
from .registry import register_agent


@register_agent("guardian")
class GuardianAgent:
    """Insert well-being reminders into task lists."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "GuardianAgent()"

    def add_nudges(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return tasks with periodic break reminders."""
        from ..capabilities.wellness import add_wellness_nudges

        return add_wellness_nudges(tasks)
