"""Chronos agent — reactive schedule manager.

Subscribes to calendar and task events to detect conflicts, learn from
estimate accuracy, and adapt schedules. Preserves the original
``create_schedule()`` method for backward compatibility.
"""

from __future__ import annotations

import logging
from typing import Any

from .base import BaseAgent
from .registry import register_agent
from ..events import Event, EventBus, Topics

logger = logging.getLogger(__name__)


@register_agent("chronos")
class ChronosAgent(BaseAgent):
    """Simple scheduler that assigns tasks into hourly blocks."""

    name = "chronos"

    def __init__(self) -> None:
        pass

    def __repr__(self) -> str:
        return "ChronosAgent()"

    # -- BaseAgent interface -------------------------------------------------

    async def run(self, context) -> Any:
        """Create schedule and check for calendar conflicts."""
        tasks = context.tasks or []
        schedule = self.create_schedule(tasks)

        total_hours = sum(t.get("estimate_h", 1) for t in tasks)
        max_daily = context.energy_config.max_daily_hours
        if total_hours > max_daily * 3:
            context.set_signal("deadline_at_risk", True)

        return schedule

    def can_contribute(self, context) -> bool:
        return True

    # -- backward compat (deterministic, no LLM) ----------------------------

    def create_schedule(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Create a deterministic daily schedule for the given tasks."""
        from ..capabilities.productivity import create_schedule

        return create_schedule(tasks)

    # -- reactive event subscriptions ----------------------------------------

    def register_subscriptions(self, bus: EventBus) -> None:
        """Wire up event handlers on the given bus."""
        bus.subscribe("calendar.*", self._on_calendar_event)
        bus.subscribe(Topics.TASK_ESTIMATE_EXCEEDED, self._on_estimate_exceeded)
        bus.subscribe(Topics.PLAN_CREATED, self._on_plan_created)

    async def _on_calendar_event(self, event: Event) -> None:
        """Handle calendar changes — check for conflicts."""
        logger.debug("Chronos: calendar event %s", event.topic)
        # future: check new/changed events against scheduled tasks

    async def _on_estimate_exceeded(self, event: Event) -> None:
        """Record timing data when a task exceeds its estimate."""
        logger.debug("Chronos: estimate exceeded for %s", event.data.get("task_title"))

        try:
            from ..estimate_learning import TaskTimingRecord, record_task_timing

            record = TaskTimingRecord(
                user_id=event.data.get("user_id", "default"),
                session_id=event.session_id or "",
                task_title=event.data.get("task_title", ""),
                task_category=event.data.get("task_category", "general"),
                estimated_hours=event.data.get("estimated_hours", 1.0),
                actual_hours=event.data.get("actual_hours", 1.0),
                ratio=event.data.get("actual_hours", 1.0)
                / max(event.data.get("estimated_hours", 1.0), 0.01),
            )
            await record_task_timing(record)
        except Exception:
            logger.debug("Chronos: failed to record timing", exc_info=True)

    async def _on_plan_created(self, event: Event) -> None:
        """Check new plan against calendar for conflicts."""
        logger.debug("Chronos: new plan created, checking conflicts")
        # future: use calendar_provider to check for scheduling conflicts
