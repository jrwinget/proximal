from __future__ import annotations
from typing import List, Dict
from . import PlannerAgent, register_agent
from packages.core.agents import _json
from packages.core.memory import client as mem


@register_agent("scribe")
class ScribeAgent(PlannerAgent):
    """Persist plans into shared memory."""

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "ScribeAgent()"

    def record_plan(self, plan: List[Dict]) -> str:
        """Store the plan in memory and return confirmation."""
        mem.batch.add_data_object({"role": "scribe", "content": _json(plan)}, "Memory")
        return "recorded"
