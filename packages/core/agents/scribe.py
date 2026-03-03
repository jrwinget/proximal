from __future__ import annotations
from typing import Any, List, Dict
from .base import BaseAgent
from .registry import register_agent
from .planner import _json
from .. import memory


@register_agent("scribe")
class ScribeAgent(BaseAgent):
    """Persist plans into shared memory."""

    name = "scribe"

    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return "ScribeAgent()"

    async def run(self, context) -> Any:
        """Persist the full shared context to storage."""
        tasks = context.tasks or []
        self.record_plan(tasks)
        return {"saved": True, "task_count": len(tasks)}

    def can_contribute(self, context) -> bool:
        return True

    def record_plan(self, plan: List[Dict]) -> str:
        """Store the plan in memory and return confirmation."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        coro = memory.store("scribe", _json(plan))
        if loop and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                pool.submit(asyncio.run, coro).result()
        else:
            asyncio.run(coro)
        return "recorded"
