from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .base import BaseAgent
from .registry import register_agent

logger = logging.getLogger(__name__)


@register_agent("focusbuddy")
class FocusBuddyAgent(BaseAgent):
    """Execution companion — focus sessions, check-ins, transitions,
    momentum tracking, retrospectives, and body-doubling presence."""

    name = "focusbuddy"

    def __init__(self) -> None:  # pragma: no cover - trivial
        self._completion_times: list[datetime] = []
        self._tasks_planned: int = 0
        self._tasks_completed: int = 0
        self._session_start: Optional[datetime] = None

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "FocusBuddyAgent()"

    # -- orchestration entry point -------------------------------------------

    async def run(self, context) -> Any:
        """Create focus sessions adapted to energy and user profile."""
        tasks = context.tasks or []
        energy = context.energy_config
        profile = context.user_profile

        # blend user preference with energy config limits
        base = self._compute_base_duration(profile, energy)
        focus_style = getattr(profile, "focus_style", "variable")
        low_energy = context.get_signal("low_energy_mode", False)

        sessions = []
        for t in tasks:
            duration, break_after, check_in = self._apply_focus_style(
                base,
                focus_style,
            )
            # shorten sessions and force breaks in low-energy mode
            if low_energy:
                duration = max(10, int(duration * 0.6))
                break_after = True
            sessions.append(
                {
                    "task": t.get("title", ""),
                    "duration_min": duration,
                    "focus_style": focus_style,
                    "break_after": break_after,
                    "check_in": check_in,
                }
            )
        return sessions

    # -- profile helpers -----------------------------------------------------

    @staticmethod
    def _compute_base_duration(profile, energy) -> int:
        """Blend preferred_session_minutes with energy config bounds."""
        preferred = getattr(profile, "preferred_session_minutes", None)
        if preferred is None:
            return energy.session_duration_minutes
        # use whichever is larger, capped by energy max
        base = max(preferred, energy.session_duration_minutes)
        return min(base, energy.max_task_duration_minutes)

    @staticmethod
    def _apply_focus_style(
        base: int,
        style: str,
    ) -> tuple[int, bool, bool]:
        """Return (duration, break_after, check_in) for the given style."""
        if style == "hyperfocus":
            return int(base * 1.5), False, False
        if style == "short-burst":
            return max(10, int(base * 0.6)), True, False
        # "variable" or any unknown style
        return base, True, True

    def can_contribute(self, context) -> bool:
        return True

    def create_sessions(self, tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Return simple 25-minute sessions for each task."""
        from ..capabilities.productivity import create_focus_sessions

        return create_focus_sessions(tasks)

    # -- reactive event subscriptions ----------------------------------------

    def register_subscriptions(self, bus) -> None:
        """Wire up event handlers on the given bus."""
        from ..events import Topics

        bus.subscribe(Topics.SESSION_TASK_STARTED, self.on_event)
        bus.subscribe(Topics.SESSION_TASK_COMPLETED, self.on_event)
        bus.subscribe(Topics.SESSION_STARTED, self.on_event)
        bus.subscribe(Topics.SESSION_ENDED, self.on_event)

    # -- reactive event handler (2.1, 2.3, 2.4) -----------------------------

    async def on_event(self, event) -> None:
        """Handle reactive events from the event bus.

        Subscribed topics: - ``session.task_started`` — emit a mid-session
        check-in - ``session.task_completed`` — track momentum -
        ``session.started`` — initialise session tracking - ``session.ended`` —
        generate retrospective
        """
        from ..events import Topics

        if event.topic == Topics.SESSION_TASK_STARTED:
            await self._handle_task_started(event)
        elif event.topic == Topics.SESSION_TASK_COMPLETED:
            await self._handle_task_completed(event)
        elif event.topic == Topics.SESSION_STARTED:
            self._handle_session_started(event)
        elif event.topic == Topics.SESSION_ENDED:
            await self._handle_session_ended(event)

    # -- 2.1  mid-session check-ins -----------------------------------------

    async def _handle_task_started(self, event) -> None:
        """Emit a check-in event adapted to focus_style and
        transition_difficulty."""
        from ..events import Event, Topics, get_event_bus

        data = event.data or {}
        focus_style = data.get("focus_style", "variable")
        transition_difficulty = data.get("transition_difficulty", "moderate")

        checkin = self._build_checkin(focus_style, transition_difficulty)

        bus = get_event_bus()
        await bus.publish(
            Event(
                topic=Topics.FOCUSBUDDY_CHECKIN,
                source="focusbuddy",
                data=checkin,
                session_id=event.session_id,
            )
        )

    @staticmethod
    def _build_checkin(
        focus_style: str,
        transition_difficulty: str,
    ) -> dict[str, Any]:
        """Build check-in payload based on style and difficulty.

        Parameters
        ----------
        focus_style : str
            "hyperfocus", "variable", or "short-burst".
        transition_difficulty : str
            "low", "moderate", or "high".

        Returns
        -------
        dict
            Check-in data with message, interval, and intensity.
        """
        # base intervals in minutes per style
        intervals = {
            "hyperfocus": 45,
            "variable": 20,
            "short-burst": 10,
        }
        messages = {
            "hyperfocus": "Still going strong — take a breath when ready.",
            "variable": "Quick check — how's the focus?",
            "short-burst": "Session boundary — nice work on that burst.",
        }
        intensities = {
            "hyperfocus": "minimal",
            "variable": "moderate",
            "short-burst": "full",
        }

        interval = intervals.get(focus_style, 20)

        # adjust interval for high transition difficulty
        if transition_difficulty == "high":
            interval = max(10, interval - 5)
        elif transition_difficulty == "low":
            interval = interval + 5

        return {
            "message": messages.get(focus_style, messages["variable"]),
            "interval_min": interval,
            "intensity": intensities.get(focus_style, "moderate"),
            "focus_style": focus_style,
            "transition_difficulty": transition_difficulty,
        }

    # -- 2.2  transition support ---------------------------------------------

    def build_transition(
        self,
        completed_task: str,
        next_task: str,
        transition_difficulty: str = "moderate",
    ) -> dict[str, Any]:
        """Generate a transition message between tasks.

        Parameters
        ----------
        completed_task : str
            Title of the completed task.
        next_task : str
            Title of the upcoming task.
        transition_difficulty : str
            "low", "moderate", or "high".

        Returns
        -------
        dict
            Transition data with message, steps, and break recommendation.
        """
        if transition_difficulty == "low":
            return {
                "message": f"Done with '{completed_task}'. Next up: '{next_task}'.",
                "steps": [],
                "break_recommended": False,
                "difficulty": "low",
            }

        if transition_difficulty == "high":
            return {
                "message": (
                    f"Great work finishing '{completed_task}'. "
                    f"Before moving on, take a moment to close "
                    f"that mental context."
                ),
                "steps": [
                    f"Save or note where you left off on '{completed_task}'",
                    "Take a 2-3 minute break — stretch, breathe",
                    f"Preview: '{next_task}' — think about what "
                    f"you'll need to get started",
                    "When ready, say 'go' to begin",
                ],
                "break_recommended": True,
                "difficulty": "high",
            }

        # moderate (default)
        return {
            "message": (
                f"Finished '{completed_task}'. The next task is "
                f"'{next_task}' — take a breath and shift gears."
            ),
            "steps": [
                f"'{next_task}' involves a context switch — gather what you need first",
            ],
            "break_recommended": False,
            "difficulty": "moderate",
        }

    async def emit_transition(
        self,
        completed_task: str,
        next_task: str,
        transition_difficulty: str,
        context=None,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Build and publish a transition event.

        Also sets or clears ``transition_in_progress`` on the context.

        Parameters
        ----------
        completed_task : str
            Title of the completed task.
        next_task : str
            Title of the upcoming task.
        transition_difficulty : str
            "low", "moderate", or "high".
        context : SharedContext or None
            If provided, sets ``transition_in_progress`` signal.
        session_id : str or None
            Session identifier for the event.

        Returns
        -------
        dict
            The transition payload.
        """
        from ..events import Event, Topics, get_event_bus

        transition = self.build_transition(
            completed_task, next_task, transition_difficulty
        )

        if context is not None:
            context.set_signal("transition_in_progress", True)

        bus = get_event_bus()
        await bus.publish(
            Event(
                topic=Topics.FOCUSBUDDY_TRANSITION,
                source="focusbuddy",
                data=transition,
                session_id=session_id,
            )
        )

        return transition

    def clear_transition(self, context) -> None:
        """Clear the transition_in_progress signal."""
        context.set_signal("transition_in_progress", False)

    # -- 2.3  progress momentum tracking ------------------------------------

    def _handle_session_started(self, event) -> None:
        """Reset tracking state when a new session starts."""
        self._completion_times = []
        self._tasks_planned = event.data.get("tasks_planned", 0)
        self._tasks_completed = 0
        self._session_start = datetime.now(timezone.utc)

    async def _handle_task_completed(self, event) -> None:
        """Record completion timestamp and increment counter."""
        now = datetime.now(timezone.utc)
        self._completion_times.append(now)
        self._tasks_completed += 1

    def calculate_momentum(
        self,
        completion_times: list[datetime] | None = None,
        *,
        _now: datetime | None = None,
    ) -> dict[str, Any]:
        """Calculate momentum from task completion timestamps.

        Parameters
        ----------
        completion_times : list[datetime] or None
            Overrides internal tracking (useful for testing).
        _now : datetime or None
            Override current time (testing).

        Returns
        -------
        dict
            Keys: ``tasks_per_hour``, ``trend``, ``signal``.
        """
        times = (
            completion_times if completion_times is not None else self._completion_times
        )

        if len(times) < 2:
            return {
                "tasks_per_hour": 0.0,
                "trend": "insufficient_data",
                "signal": None,
            }

        now = _now or datetime.now(timezone.utc)
        first = times[0]
        elapsed_hours = (now - first).total_seconds() / 3600
        if elapsed_hours <= 0:
            elapsed_hours = 0.01  # avoid division by zero

        tasks_per_hour = len(times) / elapsed_hours

        # trend from recent half vs first half
        mid = len(times) // 2
        if mid < 1:
            trend = "steady"
        else:
            first_half = times[:mid]
            second_half = times[mid:]
            first_rate = self._rate(first_half)
            second_rate = self._rate(second_half)
            if second_rate > first_rate * 1.2:
                trend = "accelerating"
            elif second_rate < first_rate * 0.8:
                trend = "decelerating"
            else:
                trend = "steady"

        # determine signal
        signal = self._momentum_signal(tasks_per_hour, trend)

        return {
            "tasks_per_hour": round(tasks_per_hour, 2),
            "trend": trend,
            "signal": signal,
        }

    @staticmethod
    def _rate(times: list[datetime]) -> float:
        """Completions per hour within a time slice."""
        if len(times) < 2:
            return 1.0
        span = (times[-1] - times[0]).total_seconds() / 3600
        if span <= 0:
            return float(len(times))
        return len(times) / span

    @staticmethod
    def _momentum_signal(tasks_per_hour: float, trend: str) -> str | None:
        """Derive a signal name from momentum metrics."""
        if trend == "accelerating" and tasks_per_hour >= 1.0:
            return "momentum_high"
        if trend == "decelerating" and tasks_per_hour < 1.0:
            return "momentum_stalling"
        if trend == "accelerating" and tasks_per_hour < 1.0:
            return "momentum_recovering"
        if trend == "steady" and tasks_per_hour >= 2.0:
            return "momentum_high"
        return None

    def apply_momentum_signals(self, context) -> dict[str, Any]:
        """Calculate momentum and set signals on context.

        Parameters
        ----------
        context : SharedContext
            The shared workflow context.

        Returns
        -------
        dict
            The momentum data.
        """
        momentum = self.calculate_momentum()

        # clear previous momentum signals
        for sig in (
            "momentum_high",
            "momentum_stalling",
            "momentum_recovering",
        ):
            context.set_signal(sig, False)

        if momentum["signal"]:
            context.set_signal(momentum["signal"], True)

        return momentum

    # -- 2.4  session retrospective ------------------------------------------

    async def _handle_session_ended(self, event) -> None:
        """Generate and publish a retrospective on session end."""
        from ..events import Event, Topics, get_event_bus

        retro = self.build_retrospective(
            tasks_planned=event.data.get("tasks_planned", self._tasks_planned),
            tasks_completed=event.data.get("tasks_completed", self._tasks_completed),
            estimated_minutes=event.data.get("estimated_minutes"),
            actual_minutes=event.data.get("actual_minutes"),
            remaining_tasks=event.data.get("remaining_tasks", []),
            celebration_style=event.data.get("celebration_style", "quiet"),
        )

        bus = get_event_bus()
        await bus.publish(
            Event(
                topic=Topics.FOCUSBUDDY_RETROSPECTIVE,
                source="focusbuddy",
                data=retro,
                session_id=event.session_id,
            )
        )

    @staticmethod
    def build_retrospective(
        *,
        tasks_planned: int = 0,
        tasks_completed: int = 0,
        estimated_minutes: float | None = None,
        actual_minutes: float | None = None,
        remaining_tasks: list[str] | None = None,
        celebration_style: str = "quiet",
    ) -> dict[str, Any]:
        """Build a structured session retrospective.

        Parameters
        ----------
        tasks_planned : int
            Number of tasks originally planned.
        tasks_completed : int
            Number of tasks completed.
        estimated_minutes : float or None
            Total estimated time.
        actual_minutes : float or None
            Total actual time.
        remaining_tasks : list[str] or None
            Titles of unfinished tasks.
        celebration_style : str
            "quiet", "enthusiastic", or "data-driven".

        Returns
        -------
        dict
            Retrospective data.
        """
        remaining = remaining_tasks or []

        # completion ratio
        ratio = tasks_completed / tasks_planned if tasks_planned > 0 else 0.0

        # timing accuracy
        timing_accuracy = None
        if (
            estimated_minutes is not None
            and actual_minutes is not None
            and estimated_minutes > 0
        ):
            timing_accuracy = round(actual_minutes / estimated_minutes, 2)

        # restart point
        restart_point = (
            f"Start with '{remaining[0]}'"
            if remaining
            else "All tasks completed — pick a new goal"
        )

        # celebration message
        celebration = _celebration_for_retro(ratio, tasks_completed, celebration_style)

        return {
            "tasks_planned": tasks_planned,
            "tasks_completed": tasks_completed,
            "completion_ratio": round(ratio, 2),
            "timing_accuracy": timing_accuracy,
            "restart_point": restart_point,
            "remaining_tasks": remaining,
            "celebration": celebration,
            "celebration_style": celebration_style,
        }

    # -- 2.5  body-doubling presence mode ------------------------------------

    @staticmethod
    def build_presence_tick(
        focus_style: str = "variable",
        energy_level: str = "medium",
        *,
        elapsed_minutes: int = 0,
    ) -> dict[str, Any]:
        """Build a single presence-mode tick payload.

        Parameters
        ----------
        focus_style : str
            "hyperfocus", "variable", or "short-burst".
        energy_level : str
            "low", "medium", or "high".
        elapsed_minutes : int
            Minutes elapsed in the session.

        Returns
        -------
        dict
            Presence tick with message, interval, and mode flag.
        """
        # interval in minutes between presence signals
        intervals = {
            "hyperfocus": 30,
            "variable": 15,
            "short-burst": 8,
        }
        # low energy = less frequent pings
        energy_mult = {"low": 1.5, "medium": 1.0, "high": 0.8}

        base_interval = intervals.get(focus_style, 15)
        mult = energy_mult.get(energy_level, 1.0)
        interval = max(5, int(base_interval * mult))

        messages = [
            "Still here with you.",
            "Working alongside you.",
            "You're not alone — keep going.",
            "Right here if you need anything.",
        ]
        # rotate message by elapsed time
        idx = (elapsed_minutes // interval) % len(messages)

        return {
            "message": messages[idx],
            "interval_min": interval,
            "presence_mode": True,
            "focus_style": focus_style,
            "energy_level": energy_level,
            "elapsed_minutes": elapsed_minutes,
        }

    async def emit_presence_tick(
        self,
        focus_style: str = "variable",
        energy_level: str = "medium",
        elapsed_minutes: int = 0,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Build and publish a presence-mode tick event.

        Parameters
        ----------
        focus_style : str
            "hyperfocus", "variable", or "short-burst".
        energy_level : str
            "low", "medium", or "high".
        elapsed_minutes : int
            Minutes elapsed in the session.
        session_id : str or None
            Session identifier.

        Returns
        -------
        dict
            The presence tick payload.
        """
        from ..events import Event, Topics, get_event_bus

        tick = self.build_presence_tick(
            focus_style, energy_level, elapsed_minutes=elapsed_minutes
        )

        bus = get_event_bus()
        await bus.publish(
            Event(
                topic=Topics.FOCUSBUDDY_PRESENCE,
                source="focusbuddy",
                data=tick,
                session_id=session_id,
            )
        )

        return tick


# -- module-level helpers (not methods, to keep class lean) ------------------


def _celebration_for_retro(
    ratio: float,
    tasks_completed: int,
    style: str,
) -> str:
    """Return a celebration string for the retrospective.

    Parameters
    ----------
    ratio : float
        Completion ratio (0.0 to 1.0+).
    tasks_completed : int
        Number completed.
    style : str
        "quiet", "enthusiastic", or "data-driven".
    """
    if style == "enthusiastic":
        if ratio >= 1.0:
            return "You crushed it — every single task done! That's amazing!"
        if ratio >= 0.5:
            return (
                f"Great momentum — {tasks_completed} tasks "
                f"down! Keep that energy rolling."
            )
        return "You showed up and made progress. That matters!"

    if style == "data-driven":
        pct = int(ratio * 100)
        return (
            f"{tasks_completed} tasks completed "
            f"({pct}% of planned). "
            f"{'On track.' if ratio >= 0.8 else 'Room to adjust estimates next time.'}"
        )

    # quiet (default)
    if ratio >= 1.0:
        return "All tasks done."
    if ratio >= 0.5:
        return f"{tasks_completed} tasks completed. Good session."
    return "Progress made. Pick up where you left off next time."
