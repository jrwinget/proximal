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

        profile = context.user_profile
        peak_hours = getattr(profile, "peak_hours", [])
        time_blindness = getattr(profile, "time_blindness", "low")

        # reorder high-priority tasks into peak-hour slots
        if peak_hours:
            schedule = self._apply_peak_hours(
                schedule, peak_hours, tasks,
            )

        # add buffers and transition time for time blindness
        if time_blindness in ("moderate", "high"):
            schedule = self._apply_time_buffers(
                schedule, time_blindness,
            )

        # in low-energy mode, cap schedule to fewer hours
        low_energy = context.get_signal("low_energy_mode", False)
        if low_energy:
            schedule = self._trim_for_low_energy(
                schedule, context.energy_config.max_daily_hours,
            )

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

    # -- profile-aware schedule helpers --------------------------------------

    @staticmethod
    def _apply_peak_hours(
        schedule: list[dict[str, Any]],
        peak_hours: list[int],
        tasks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Reorder schedule so high-priority tasks land in peak hours."""
        if not schedule or not peak_hours:
            return schedule

        peak_set = set(peak_hours)

        # identify peak-hour slot indices and high-priority slot indices
        peak_indices: list[int] = []
        high_priority_indices: list[int] = []

        for i, entry in enumerate(schedule):
            start_str = entry.get("start", "")
            if not start_str:
                continue
            try:
                hour = int(start_str.split(":")[0])
            except (ValueError, IndexError):
                continue

            # skip break entries
            task_data = entry.get("task", {})
            title = (
                task_data.get("title", "")
                if isinstance(task_data, dict)
                else str(task_data)
            )
            if title.lower() == "break":
                continue

            if hour in peak_set:
                peak_indices.append(i)

            # check priority from the original task data
            priority = ""
            if isinstance(task_data, dict):
                priority = task_data.get("priority", "")
            if priority in ("P0", "P1"):
                high_priority_indices.append(i)

        # if no priority info, treat first half as high-priority
        if not high_priority_indices:
            non_break = [
                i for i in range(len(schedule))
                if not (
                    isinstance(schedule[i].get("task", {}), dict)
                    and schedule[i].get("task", {}).get(
                        "title", ""
                    ).lower() == "break"
                )
            ]
            high_priority_indices = non_break[: len(non_break) // 2]

        # swap task data (not times) between peak and high-priority slots
        swaps = min(len(peak_indices), len(high_priority_indices))
        for s in range(swaps):
            pi = peak_indices[s]
            hi = high_priority_indices[s]
            if pi != hi:
                schedule[pi]["task"], schedule[hi]["task"] = (
                    schedule[hi]["task"],
                    schedule[pi]["task"],
                )

        return schedule

    @staticmethod
    def _apply_time_buffers(
        schedule: list[dict[str, Any]],
        time_blindness: str,
    ) -> list[dict[str, Any]]:
        """Add time buffers and notes based on time blindness severity."""
        if time_blindness == "low":
            return schedule

        buffer_pct = 0.15 if time_blindness == "moderate" else 0.30
        add_transitions = time_blindness == "high"
        result: list[dict[str, Any]] = []
        remaining = len([
            e for e in schedule
            if not (
                isinstance(e.get("task", {}), dict)
                and e.get("task", {}).get("title", "").lower()
                in ("break", "transition time")
            )
        ])

        for i, entry in enumerate(schedule):
            task_data = entry.get("task", {})
            title = (
                task_data.get("title", "")
                if isinstance(task_data, dict)
                else str(task_data)
            )

            # skip breaks / transitions for buffering
            if title.lower() in ("break", "transition time"):
                result.append(entry)
                continue

            # parse start/end to compute buffer
            start_str = entry.get("start", "")
            end_str = entry.get("end", "")
            buffered = dict(entry)

            if start_str and end_str:
                try:
                    sh, sm = map(int, start_str.split(":"))
                    eh, em = map(int, end_str.split(":"))
                    duration_min = (eh * 60 + em) - (sh * 60 + sm)
                    buffer_min = int(duration_min * buffer_pct)
                    new_end = eh * 60 + em + buffer_min
                    buffered["end"] = (
                        f"{new_end // 60:02d}:{new_end % 60:02d}"
                    )
                except (ValueError, IndexError):
                    pass

            # add concrete time note
            if remaining > 0:
                buffered["time_note"] = (
                    f"about {remaining} session"
                    f"{'s' if remaining != 1 else ''} left"
                )
            remaining -= 1

            result.append(buffered)

            # insert transition entries for high time blindness
            if add_transitions and i < len(schedule) - 1:
                t_start = buffered.get("end", end_str)
                if t_start:
                    try:
                        th, tm = map(int, t_start.split(":"))
                        t_end_min = th * 60 + tm + 5
                        t_end = (
                            f"{t_end_min // 60:02d}:"
                            f"{t_end_min % 60:02d}"
                        )
                    except (ValueError, IndexError):
                        t_end = t_start
                    result.append({
                        "task": {"title": "Transition time"},
                        "start": t_start,
                        "end": t_end,
                    })

        return result

    @staticmethod
    def _trim_for_low_energy(
        schedule: list[dict[str, Any]], max_daily: float,
    ) -> list[dict[str, Any]]:
        """Reduce schedule to half the normal daily hours."""
        cap_hours = max(1.0, max_daily * 0.5)
        result: list[dict[str, Any]] = []
        accumulated = 0.0
        for entry in schedule:
            start = entry.get("start", "")
            end = entry.get("end", "")
            if start and end:
                try:
                    sh, sm = map(int, start.split(":"))
                    eh, em = map(int, end.split(":"))
                    dur_h = ((eh * 60 + em) - (sh * 60 + sm)) / 60
                except (ValueError, IndexError):
                    dur_h = 1.0
            else:
                dur_h = 1.0
            if accumulated + dur_h > cap_hours:
                break
            result.append(entry)
            accumulated += dur_h
        return result

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
