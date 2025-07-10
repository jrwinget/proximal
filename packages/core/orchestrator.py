from __future__ import annotations
import asyncio
from typing import Any, Dict, List
from .agents import plan_llm
from .agents import AGENT_REGISTRY, PlannerAgent


class Orchestrator:
    """Coordinate planning and scheduling agents."""

    def __init__(self) -> None:
        self.registry = AGENT_REGISTRY

    def _get_agent(self, name: str) -> PlannerAgent:
        cls = self.registry.get(name)
        if not cls:
            raise ValueError(f"Agent '{name}' not found in registry")
        return cls()

    async def _call(self, agent: PlannerAgent, method: str, *args: Any) -> Any:
        fn = getattr(agent, method)
        if asyncio.iscoroutinefunction(fn):
            return await fn(*args)
        return await asyncio.to_thread(fn, *args)

    async def run(self, goal: str) -> Dict[str, Any]:
        """Generate a plan and aggregate outputs from all agents."""
        tasks_result = await plan_llm({"goal": goal})
        tasks = [t.model_dump() for t in tasks_result.get("tasks", [])]

        agents = {
            "chronos": ("create_schedule", tasks),
            "guardian": ("add_nudges", tasks),
            "mentor": ("motivate", goal),
            "scribe": ("record_plan", tasks),
            "liaison": ("draft_message", goal),
            "focusbuddy": ("create_sessions", tasks),
        }

        results: Dict[str, Any] = {"plan": tasks}
        coros = []
        agent_names: List[str] = []
        for name, (method, arg) in agents.items():
            try:
                inst = self._get_agent(name)
            except ValueError:
                continue
            coros.append(self._call(inst, method, arg))
            agent_names.append(name)

        outputs = await asyncio.gather(*coros, return_exceptions=True)
        for name, value in zip(agent_names, outputs):
            results[name] = value if not isinstance(value, Exception) else None

        # backward compatible key for scheduler
        if "chronos" in results:
            results["schedule"] = results["chronos"]

        return results

    def run_sync(self, goal: str) -> Dict[str, Any]:
        """Synchronous wrapper for the async run method."""
        return asyncio.run(self.run(goal))
