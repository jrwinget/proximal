from __future__ import annotations

from typing import Any
from .registry import register_agent


@register_agent("chronos")
class ChronosAgent:
    """Simple scheduler that assigns tasks into hourly blocks."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "ChronosAgent()"

    def create_schedule(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Create a deterministic daily schedule for the given tasks."""
        from ..capabilities.productivity import create_schedule

        return create_schedule(tasks)
