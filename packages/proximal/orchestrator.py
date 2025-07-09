from __future__ import annotations
import asyncio
from typing import Dict, List
from packages.core.agents import plan_llm
from .agents import AGENT_REGISTRY, BaseAgent


class Orchestrator:
    """Coordinate planning and scheduling agents."""

    def __init__(self) -> None:
        self.registry = AGENT_REGISTRY

    def _get_agent(self, name: str) -> BaseAgent:
        cls = self.registry.get(name)
        if not cls:
            raise ValueError(f"Agent '{name}' not found in registry")
        return cls()

    async def run(self, goal: str) -> Dict[str, List[Dict]]:
        """Generate a plan and schedule for the given goal."""
        tasks_result = await plan_llm({"goal": goal})
        tasks = [t.model_dump() for t in tasks_result.get("tasks", [])]
        chronos = self._get_agent("chronos")
        schedule = chronos.create_schedule(tasks)
        return {"plan": tasks, "schedule": schedule}

    def run_sync(self, goal: str) -> Dict[str, List[Dict]]:
        """Synchronous wrapper for the async run method."""
        return asyncio.run(self.run(goal))
