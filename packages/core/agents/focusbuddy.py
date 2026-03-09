from __future__ import annotations

from typing import Any

from .base import BaseAgent
from .registry import register_agent


@register_agent("focusbuddy")
class FocusBuddyAgent(BaseAgent):
    """Create short focus sessions for each task."""

    name = "focusbuddy"

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "FocusBuddyAgent()"

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
