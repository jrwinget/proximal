"""Guardian agent — stateful reactive wellness monitor.

Subscribes to session and task events to track wellness observations,
detect cross-session patterns, and escalate when needed. Preserves the
original ``add_nudges()`` method for backward compatibility.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from .base import BaseAgent
from .registry import register_agent
from ..events import Event, EventBus, Topics
from ..models import (
    EscalationLevel,
    WellnessObservation,
    WellnessObservationType,
)

logger = logging.getLogger(__name__)


@register_agent("guardian")
class GuardianAgent(BaseAgent):
    """Insert well-being reminders and monitor wellness patterns."""

    name = "guardian"

    def __init__(self) -> None:
        self._active_sessions: dict[str, datetime] = {}

    def __repr__(self) -> str:
        return "GuardianAgent()"

    # -- BaseAgent interface -------------------------------------------------

    async def run(self, context, *, _now: datetime | None = None) -> Any:
        """Assess overwhelm signals and inject wellness guidance."""
        tasks = context.tasks or []
        profile = context.user_profile

        # proactively activate low-energy mode on low-energy days
        is_low_day = self._is_low_energy_day(profile, _now=_now)
        if is_low_day:
            context.set_signal("low_energy_mode", True)
            await self._emit_low_energy_nudge()

        # reduce effective threshold on low-energy days (~30%)
        threshold = profile.overwhelm_threshold
        if is_low_day:
            threshold = max(1, int(threshold * 0.7))

        # check if task count exceeds effective overwhelm threshold
        if len(tasks) > threshold:
            context.set_signal("overwhelm_detected", True)
            context.set_signal("low_energy_mode", True)

        # respond to deadline pressure with wellness monitoring
        deadline_risk = context.get_signal("deadline_at_risk", False)
        if deadline_risk:
            await self._emit_deadline_wellness_nudge()

        result = self.add_nudges(tasks)
        return result

    def can_contribute(self, context) -> bool:
        return True

    # -- backward compat (deterministic, no LLM) ----------------------------

    def add_nudges(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return tasks with periodic break reminders."""
        from ..capabilities.wellness import add_wellness_nudges

        return add_wellness_nudges(tasks)

    # -- reactive event subscriptions ----------------------------------------

    def register_subscriptions(self, bus: EventBus) -> None:
        """Wire up event handlers on the given bus."""
        bus.subscribe(Topics.SESSION_STARTED, self._on_session_started)
        bus.subscribe(Topics.SESSION_TASK_COMPLETED, self._on_task_completed)
        bus.subscribe(Topics.SESSION_ENDED, self._on_session_ended)

    async def _on_session_started(self, event: Event) -> None:
        """Record the start of a session for wellness tracking."""
        session_id = event.session_id or ""
        self._active_sessions[session_id] = event.timestamp

        now = event.timestamp
        is_late = now.hour >= 22

        observation = WellnessObservation(
            user_id=event.data.get("user_id", "default"),
            session_id=session_id,
            observation_type=WellnessObservationType.session_start,
            data={"goal": event.data.get("goal", ""), "is_late": is_late},
            timestamp=now,
        )

        if is_late:
            late_obs = WellnessObservation(
                user_id=event.data.get("user_id", "default"),
                session_id=session_id,
                observation_type=WellnessObservationType.late_session,
                data={},
                timestamp=now,
            )
            await self._store_observation(late_obs)

        await self._store_observation(observation)
        logger.debug("Guardian: session started %s", session_id)

    async def _on_task_completed(self, event: Event) -> None:
        """Record task completion and check for nudges."""
        session_id = event.session_id or ""
        observation = WellnessObservation(
            user_id=event.data.get("user_id", "default"),
            session_id=session_id,
            observation_type=WellnessObservationType.task_completed,
            data=event.data,
            timestamp=event.timestamp,
        )
        await self._store_observation(observation)

    async def _on_session_ended(self, event: Event) -> None:
        """Record session end, compute summary, and run pattern detection."""
        session_id = event.session_id or ""
        observation = WellnessObservation(
            user_id=event.data.get("user_id", "default"),
            session_id=session_id,
            observation_type=WellnessObservationType.session_end,
            data=event.data,
            timestamp=event.timestamp,
        )
        await self._store_observation(observation)
        self._active_sessions.pop(session_id, None)
        logger.debug("Guardian: session ended %s", session_id)

    # -- escalation ----------------------------------------------------------

    def build_escalation_message(
        self, level: EscalationLevel, context: dict[str, Any] | None = None
    ) -> str:
        """Generate a wellness intervention message."""
        templates = {
            EscalationLevel.gentle_nudge: (
                "Hey, just a gentle reminder to take a short break when you can. "
                "Even a minute of stretching helps."
            ),
            EscalationLevel.firm_reminder: (
                "It looks like you've been working for a while without a break. "
                "Please take 5-10 minutes to rest — you'll come back sharper."
            ),
            EscalationLevel.escalated_warning: (
                "I'm concerned about your work pattern. Extended sessions without "
                "breaks can lead to burnout. Please take a proper break now."
            ),
            EscalationLevel.session_end_suggestion: (
                "You've been at it for a long time. Consider wrapping up for now "
                "and picking this up fresh tomorrow. Rest is productive too."
            ),
        }
        return templates.get(level, templates[EscalationLevel.gentle_nudge])

    # -- profile helpers -----------------------------------------------------

    @staticmethod
    def _is_low_energy_day(
        profile, *, _now: datetime | None = None,
    ) -> bool:
        """Check if the current day is in the user's low-energy days."""
        low_days = getattr(profile, "low_energy_days", [])
        if not low_days:
            return False
        now = _now or datetime.now()
        today_name = now.strftime("%A")
        # case-insensitive comparison
        return today_name.lower() in [d.lower() for d in low_days]

    async def _emit_low_energy_nudge(self) -> None:
        """Emit a gentle nudge event for low-energy days."""
        try:
            from ..events import Event, get_event_bus

            bus = get_event_bus()
            await bus.publish(Event(
                topic=Topics.GUARDIAN_NUDGE,
                source="guardian",
                data={
                    "type": "low_energy_day",
                    "message": (
                        "It's a low-energy day — be gentle "
                        "with yourself today."
                    ),
                },
            ))
        except Exception:
            logger.debug(
                "Guardian: failed to emit low-energy nudge",
                exc_info=True,
            )

    async def _emit_deadline_wellness_nudge(self) -> None:
        """Emit a wellness nudge when deadline pressure is detected."""
        try:
            from ..events import Event, get_event_bus

            bus = get_event_bus()
            await bus.publish(Event(
                topic=Topics.GUARDIAN_NUDGE,
                source="guardian",
                data={
                    "type": "deadline_pressure",
                    "message": (
                        "Deadline pressure detected — remember to "
                        "take breaks. Pushing too hard leads to "
                        "diminishing returns."
                    ),
                },
            ))
        except Exception:
            logger.debug(
                "Guardian: failed to emit deadline nudge",
                exc_info=True,
            )

    # -- helpers -------------------------------------------------------------

    async def _store_observation(self, observation: WellnessObservation) -> None:
        """Store observation; silently skip in test environments."""
        try:
            from ..wellness_memory import store_observation

            await store_observation(observation)
        except Exception:
            logger.debug("Guardian: failed to store observation", exc_info=True)
