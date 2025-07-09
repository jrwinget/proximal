from __future__ import annotations
from datetime import datetime, timedelta
from typing import List, Dict
from . import BaseAgent, register_agent


@register_agent("chronos")
class ChronosAgent(BaseAgent):
    """Simple scheduler that assigns tasks into hourly blocks."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "ChronosAgent()"

    def create_schedule(self, tasks: List[Dict]) -> List[Dict]:
        """Create a deterministic daily schedule for the given tasks."""
        schedule: List[Dict] = []
        current = datetime.combine(datetime.today(), datetime.min.time()).replace(
            hour=9, minute=0
        )

        for index, task in enumerate(tasks, start=1):
            end = current + timedelta(hours=1)
            schedule.append(
                {
                    "task": task,
                    "start": current.strftime("%H:%M"),
                    "end": end.strftime("%H:%M"),
                }
            )
            current = end

            if index % 3 == 0:
                break_end = current + timedelta(minutes=5)
                schedule.append(
                    {
                        "task": {"title": "Break"},
                        "start": current.strftime("%H:%M"),
                        "end": break_end.strftime("%H:%M"),
                    }
                )
                current = break_end

        return schedule
