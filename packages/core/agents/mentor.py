from __future__ import annotations

from typing import Any

from .base import BaseAgent
from .registry import register_agent


@register_agent("mentor")
class MentorAgent(BaseAgent):
    """Provide motivational coaching snippets."""

    name = "mentor"

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "MentorAgent()"

    async def run(self, context) -> Any:
        """Provide encouragement adapted to signals and user profile.

        Reads ``tone``, ``celebration_style``, and ``verbosity`` from
        ``context.user_profile`` to personalise the encouragement.
        Falls back to sensible defaults when values are missing or
        unrecognised.

        Parameters
        ----------
        context : SharedContext
            The shared orchestration context.

        Returns
        -------
        str
            A profile-aware encouragement or overwhelm message.
        """
        goal = context.goal
        profile = getattr(context, "user_profile", None)
        overwhelm = context.get_signal("overwhelm_detected", False)
        low_energy = context.get_signal("low_energy_mode", False)
        deadline_risk = context.get_signal("deadline_at_risk", False)

        if overwhelm:
            return self._overwhelm_message(goal, profile)

        if deadline_risk:
            return self._deadline_risk_message(goal, profile)

        if low_energy:
            return self._low_energy_message(goal, profile)

        return self._build_encouragement(goal, profile)

    def can_contribute(self, context) -> bool:
        return True

    def motivate(self, goal: str) -> str:
        """Return a short encouragement for the goal.

        Kept for backward compatibility with code that calls
        ``motivate()`` directly.
        """
        from ..capabilities.wellness import motivate

        return motivate(goal)

    # ------------------------------------------------------------------
    # private helpers
    # ------------------------------------------------------------------

    def _overwhelm_message(self, goal: str, profile: Any) -> str:
        """Return an overwhelm message adapted to the user's tone.

        Parameters
        ----------
        goal : str
            The user's goal text.
        profile : UserProfile | None
            The user profile (may be ``None``).

        Returns
        -------
        str
            A tone-appropriate overwhelm message.
        """
        tone = getattr(profile, "tone", "warm") if profile else "warm"

        messages = {
            "warm": (
                f"I see this feels like a lot right now. Let's just "
                f"focus on the very next small step for '{goal}'. "
                f"You've got this."
            ),
            "professional": (
                f"Current task load exceeds comfortable threshold. "
                f"Recommended: focus on the highest-priority item "
                f"for '{goal}'."
            ),
            "direct": (f"Too many tasks. Pick one thing for '{goal}' and start there."),
            "playful": (
                f"Whoa, that's a lot on the plate! Let's just grab "
                f"one bite-sized piece of '{goal}' for now."
            ),
        }
        return messages.get(tone, messages["warm"])

    def _deadline_risk_message(self, goal: str, profile: Any) -> str:
        """Supportive-under-pressure message when deadline is at risk."""
        tone = getattr(profile, "tone", "warm") if profile else "warm"
        messages = {
            "warm": (
                f"The deadline for '{goal}' is tight, but you're "
                f"making progress. Focus on the very next step — "
                f"one thing at a time."
            ),
            "professional": (
                f"Timeline for '{goal}' is at risk. Prioritise the "
                f"highest-impact item and defer what you can."
            ),
            "direct": (
                f"Deadline pressure on '{goal}'. Pick the most "
                f"critical task and ship it."
            ),
            "playful": (
                f"Clock's ticking on '{goal}', but no panic! "
                f"Grab the next thing and keep rolling."
            ),
        }
        return messages.get(tone, messages["warm"])

    def _low_energy_message(self, goal: str, profile: Any) -> str:
        """Gentler encouragement when low-energy mode is active."""
        tone = getattr(profile, "tone", "warm") if profile else "warm"
        messages = {
            "warm": (
                f"It's okay to go easy today. Even a small step "
                f"toward '{goal}' counts. Be kind to yourself."
            ),
            "professional": (
                f"Energy is low today. Consider lighter tasks "
                f"related to '{goal}' and protect your capacity."
            ),
            "direct": (
                f"Low energy day. Do one small thing for '{goal}' and call it a win."
            ),
            "playful": (
                f"Cozy mode activated! A little nibble at '{goal}' is plenty for today."
            ),
        }
        return messages.get(tone, messages["warm"])

    def _build_encouragement(self, goal: str, profile: Any) -> str:
        """Build a profile-aware encouragement message.

        Combines ``celebration_style``, ``verbosity``, and ``tone``
        from the user profile to produce a personalised message.

        Parameters
        ----------
        goal : str
            The user's goal text.
        profile : UserProfile | None
            The user profile (may be ``None``).

        Returns
        -------
        str
            A personalised encouragement string.
        """
        if profile is None:
            return self.motivate(goal)

        celebration = getattr(profile, "celebration_style", "quiet")
        verbosity = getattr(profile, "verbosity", "medium")
        tone = getattr(profile, "tone", "warm")

        # base sentences keyed by celebration style
        base = self._celebration_base(goal, celebration)
        # adapt length by verbosity
        text = self._apply_verbosity(base, goal, verbosity, tone)
        # adjust word choice by tone
        text = self._apply_tone(text, goal, tone)

        return text

    def _celebration_base(self, goal: str, style: str) -> str:
        """Return the core encouragement keyed by celebration style."""
        bases = {
            "quiet": f"Done. Moving on to '{goal}'.",
            "enthusiastic": (
                f"Yes! You're making great progress on '{goal}'! "
                f"Keep that momentum going!"
            ),
            "data-driven": (
                f"Progress update: working on '{goal}'. Stay focused on the next step."
            ),
        }
        return bases.get(style, bases["quiet"])

    def _apply_verbosity(
        self,
        base: str,
        goal: str,
        verbosity: str,
        tone: str,
    ) -> str:
        """Expand or trim the base message according to verbosity."""
        if verbosity == "minimal":
            # one short sentence only
            return base.split(".")[0] + "."

        if verbosity == "detailed":
            # add context, rationale, and next-step guidance
            extra = (
                f" Taking things one step at a time keeps progress "
                f"steady and manageable. Identify the very next "
                f"action for '{goal}' and start there. "
                f"Small wins build real momentum."
            )
            return base + extra

        # medium — return base as-is (2-3 sentences)
        return base

    def _apply_tone(self, text: str, goal: str, tone: str) -> str:
        """Lightly adjust wording to match the requested tone.

        Heavy rewrites are avoided; instead, a short tonal phrase is
        prepended for tones that differ from the neutral default.
        """
        if tone == "warm":
            # add empathetic opener when not already present
            if not text.startswith("I ") and not text.startswith("You"):
                text = "You're doing great. " + text
        elif tone == "professional":
            # keep text factual; strip exclamation marks
            text = text.replace("!", ".")
        elif tone == "direct":
            # strip filler phrases
            text = text.replace("You're doing great. ", "")
            text = text.replace("!", ".")
        elif tone == "playful":
            # add a lighthearted opener
            if not text.startswith("Nice"):
                text = "Nice work! " + text

        return text
