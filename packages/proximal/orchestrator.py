from __future__ import annotations
import asyncio
from typing import Any, Dict, List
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

    async def run(self, goal: str) -> Dict[str, Any]:
        """Generate a plan and run all registered agents."""
        tasks_result = await plan_llm({"goal": goal})
        tasks = [t.model_dump() for t in tasks_result.get("tasks", [])]

        chronos = self._get_agent("chronos")
        guardian = self._get_agent("guardian")
        mentor = self._get_agent("mentor")
        scribe = self._get_agent("scribe")
        liaison = self._get_agent("liaison")
        focusbuddy = self._get_agent("focusbuddy")

        schedule = chronos.create_schedule(tasks)

        results = await asyncio.gather(
            asyncio.to_thread(guardian.suggest_breaks, tasks),
            asyncio.to_thread(mentor.coach, goal),
            asyncio.to_thread(scribe.record, goal, tasks),
            asyncio.to_thread(liaison.compose_message, goal),
            asyncio.to_thread(focusbuddy.create_sessions, tasks),
        )

        return {
            "plan": tasks,
            "schedule": schedule,
            "breaks": results[0],
            "coaching": results[1],
            "notes": results[2],
            "message": results[3],
            "focus_sessions": results[4],
        }

    def run_sync(self, goal: str) -> Dict[str, Any]:
        """Synchronous wrapper for the async run method."""
        return asyncio.run(self.run(goal))
