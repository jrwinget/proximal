from __future__ import annotations
import asyncio
import logging
from typing import Any, Dict, List, Optional

from .agents import plan_llm
from .agents import AGENT_REGISTRY, PlannerAgent
from .observability import get_observability_logger, trace_operation
from .fault_tolerance import with_timeout
from .providers.exceptions import AgentError

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Coordinate planning and scheduling agents using supervisor pattern.

    The orchestrator acts as a supervisor, delegating tasks to specialized agents
    and aggregating their results. Follows 2025 best practices for multi-agent systems.
    """

    def __init__(self, agent_timeout: float = 30.0) -> None:
        """
        Initialize orchestrator.

        Args:
            agent_timeout: Timeout in seconds for individual agent operations
        """
        self.registry = AGENT_REGISTRY
        self.agent_timeout = agent_timeout
        self.obs_logger = get_observability_logger()

    def _get_agent(self, name: str) -> PlannerAgent:
        """Get agent instance from registry."""
        cls = self.registry.get(name)
        if not cls:
            raise ValueError(f"Agent '{name}' not found in registry")
        return cls()

    async def _call_agent_with_fault_tolerance(
        self,
        agent_name: str,
        agent: PlannerAgent,
        method: str,
        *args: Any
    ) -> Any:
        """
        Call agent method with fault tolerance and observability.

        Implements:
        - Per-node timeouts
        - Tracing and metrics
        - Error handling with graceful degradation
        """
        operation_name = f"{agent_name}.{method}"

        try:
            with trace_operation("orchestrator", "agent_call", agent=agent_name, method=method):
                fn = getattr(agent, method)

                # Execute with timeout
                if asyncio.iscoroutinefunction(fn):
                    result = await with_timeout(
                        fn(*args),
                        timeout_seconds=self.agent_timeout,
                        operation_name=operation_name
                    )
                else:
                    result = await with_timeout(
                        asyncio.to_thread(fn, *args),
                        timeout_seconds=self.agent_timeout,
                        operation_name=operation_name
                    )

                logger.info(f"Agent {agent_name} completed successfully")
                return result

        except Exception as e:
            logger.error(f"Agent {agent_name} failed: {e}", exc_info=True)
            # Graceful degradation - return None instead of crashing entire workflow
            return None

    async def run(self, goal: str) -> Dict[str, Any]:
        """
        Generate a plan and aggregate outputs from all agents.

        Implements supervisor pattern:
        1. Planner agent creates initial task breakdown
        2. Specialized agents process tasks in parallel
        3. Results are aggregated and returned

        Args:
            goal: User's high-level goal

        Returns:
            Dictionary containing results from all agents
        """
        with trace_operation("orchestrator", "run", goal=goal):
            # Step 1: Generate plan using planner agent
            logger.info(f"Orchestrator starting workflow for goal: {goal}")
            self.obs_logger.log_agent_handoff("orchestrator", "planner", {"goal": goal})

            try:
                tasks_result = await with_timeout(
                    plan_llm({"goal": goal}),
                    timeout_seconds=self.agent_timeout,
                    operation_name="planner.plan_llm"
                )
                tasks = [t.model_dump() for t in tasks_result.get("tasks", [])]
                logger.info(f"Planner generated {len(tasks)} tasks")

            except Exception as e:
                logger.error(f"Planner agent failed: {e}", exc_info=True)
                raise AgentError(f"Failed to generate plan: {e}", agent_name="planner")

            # Step 2: Define agent delegation strategy
            agents = {
                "chronos": ("create_schedule", tasks),
                "guardian": ("add_nudges", tasks),
                "mentor": ("motivate", goal),
                "scribe": ("record_plan", tasks),
                "liaison": ("draft_message", goal),
                "focusbuddy": ("create_sessions", tasks),
            }

            # Step 3: Execute agents in parallel (scatter pattern)
            results: Dict[str, Any] = {"plan": tasks}
            coros = []
            agent_names: List[str] = []

            for name, (method, arg) in agents.items():
                try:
                    inst = self._get_agent(name)
                    self.obs_logger.log_agent_handoff("orchestrator", name, {"method": method})
                    coros.append(self._call_agent_with_fault_tolerance(name, inst, method, arg))
                    agent_names.append(name)
                except ValueError as e:
                    logger.warning(f"Agent {name} not available: {e}")
                    continue

            # Step 4: Gather results (gather pattern)
            # Use return_exceptions=True for graceful degradation
            logger.info(f"Executing {len(coros)} agents in parallel")
            outputs = await asyncio.gather(*coros, return_exceptions=True)

            # Step 5: Aggregate results
            successful_agents = 0
            failed_agents = 0

            for name, value in zip(agent_names, outputs):
                if isinstance(value, Exception):
                    logger.error(f"Agent {name} raised exception: {value}")
                    results[name] = None
                    failed_agents += 1
                else:
                    results[name] = value
                    if value is not None:
                        successful_agents += 1

            logger.info(
                f"Orchestrator completed: {successful_agents} agents succeeded, "
                f"{failed_agents} failed"
            )

            # Backward compatible key for scheduler
            if "chronos" in results:
                results["schedule"] = results["chronos"]

            # Add execution metadata
            results["_metadata"] = {
                "total_agents": len(agent_names),
                "successful_agents": successful_agents,
                "failed_agents": failed_agents,
                "goal": goal
            }

            return results

    def run_sync(self, goal: str) -> Dict[str, Any]:
        """Synchronous wrapper for the async run method."""
        return asyncio.run(self.run(goal))
