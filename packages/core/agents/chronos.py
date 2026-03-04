"""Chronos agent — reactive schedule manager.

Subscribes to calendar and task events to detect conflicts, learn from
estimate accuracy, and adapt schedules. Preserves the original
``create_schedule()`` method for backward compatibility.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from .base import BaseAgent
from .registry import register_agent
from ..events import Event, EventBus, Topics, get_event_bus

if TYPE_CHECKING:
    from ..integrations.calendar_provider import CalendarProvider

logger = logging.getLogger(__name__)


@register_agent("chronos")
class ChronosAgent(BaseAgent):
    """Simple scheduler that assigns tasks into hourly blocks."""

    name = "chronos"

    def __init__(self, calendar_provider: CalendarProvider | None = None) -> None:
        from ..integrations.calendar_provider import get_calendar_provider

        if calendar_provider is not None:
            self._calendar_provider = calendar_provider
        else:
            self._calendar_provider = get_calendar_provider("stub")
        self._bus: EventBus | None = None

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
        self._bus = bus
        bus.subscribe("calendar.*", self._on_calendar_event)
        bus.subscribe(Topics.TASK_ESTIMATE_EXCEEDED, self._on_estimate_exceeded)
        bus.subscribe(Topics.PLAN_CREATED, self._on_plan_created)

    async def _on_calendar_event(self, event: Event) -> list[dict[str, Any]] | None:
        """Handle calendar changes — check for conflicts.

        Parameters
        ----------
        event : Event
            A calendar event with ``start`` and ``end`` in the data payload.

        Returns
        -------
        list[dict[str, Any]] or None
            Detected conflicts, empty list if none, or None on failure.
        """
        logger.debug("Chronos: calendar event %s", event.topic)

        try:
            return await self._check_calendar_conflicts(event)
        except Exception:
            logger.debug("Chronos: failed to check calendar conflicts", exc_info=True)
            return None

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

    async def _on_plan_created(self, event: Event) -> list[dict[str, Any]] | None:
        """Check new plan against calendar for conflicts.

        Parameters
        ----------
        event : Event
            A plan.created event with optional ``tasks`` in data.

        Returns
        -------
        list[dict[str, Any]] or None
            Detected conflicts, empty list if none, or None on failure.
        """
        logger.debug("Chronos: new plan created, checking conflicts")

        try:
            return await self._check_plan_conflicts(event)
        except Exception:
            logger.debug("Chronos: failed to check plan conflicts", exc_info=True)
            return None

    # -- calendar conflict helpers -------------------------------------------

    async def _check_calendar_conflicts(
        self, event: Event
    ) -> list[dict[str, Any]]:
        """Check a calendar event against existing events for overlaps.

        Parameters
        ----------
        event : Event
            The incoming calendar event.

        Returns
        -------
        list[dict[str, Any]]
            List of conflict dicts.
        """
        data = event.data
        start_str = data.get("start", "")
        end_str = data.get("end", "")

        if not start_str or not end_str:
            return []

        # parse iso timestamps from the event data
        new_start = datetime.fromisoformat(start_str)
        new_end = datetime.fromisoformat(end_str)

        # query the full day to catch all potential overlaps
        day_start = new_start.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)
        existing = await self._calendar_provider.get_events(day_start, day_end)

        conflicts: list[dict[str, Any]] = []
        new_title = data.get("title", "Unknown")

        for evt in existing:
            # overlap: new_start < evt.end and new_end > evt.start
            if new_start < evt.end and new_end > evt.start:
                conflicts.append({
                    "new_event": new_title,
                    "new_time": f"{new_start.isoformat()}-{new_end.isoformat()}",
                    "conflict_with": evt.title,
                    "event_time": f"{evt.start.isoformat()}-{evt.end.isoformat()}",
                })

        if conflicts:
            await self._emit_conflict(conflicts, event.topic)

        return conflicts

    async def _check_plan_conflicts(
        self, event: Event
    ) -> list[dict[str, Any]]:
        """Check plan tasks against calendar events.

        Parameters
        ----------
        event : Event
            The plan.created event with tasks in data.

        Returns
        -------
        list[dict[str, Any]]
            List of conflict dicts.
        """
        tasks = event.data.get("tasks", [])
        if not tasks:
            return []

        # get calendar events for today
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        existing = await self._calendar_provider.get_events(day_start, day_end)
        if not existing:
            return []

        conflicts: list[dict[str, Any]] = []
        for task in tasks:
            task_start = task.get("start", "")
            task_end = task.get("end", "")
            task_title = task.get("title", "")

            if not task_start or not task_end:
                continue

            for evt in existing:
                evt_start_str = evt.start.strftime("%H:%M")
                evt_end_str = evt.end.strftime("%H:%M")
                if task_start < evt_end_str and task_end > evt_start_str:
                    conflicts.append({
                        "task": task_title,
                        "task_time": f"{task_start}-{task_end}",
                        "conflict_with": evt.title,
                        "event_time": f"{evt_start_str}-{evt_end_str}",
                    })

        if conflicts:
            await self._emit_conflict(conflicts, event.topic)

        return conflicts

    async def _emit_conflict(
        self, conflicts: list[dict[str, Any]], trigger: str
    ) -> None:
        """Publish a CHRONOS_CONFLICT event on the registered bus."""
        bus = self._bus or get_event_bus()
        await bus.publish(Event(
            topic=Topics.CHRONOS_CONFLICT,
            source="chronos",
            data={"conflicts": conflicts, "trigger": trigger},
        ))
