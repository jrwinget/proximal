from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any, Dict, List

from .agents import AGENT_REGISTRY, plan_llm
from .capabilities import CAPABILITY_REGISTRY
from .events import Event, Topics, get_event_bus
from .fault_tolerance import with_timeout
from .observability import get_observability_logger, trace_operation
from .providers.exceptions import AgentError

if TYPE_CHECKING:
    from .collaboration.context import SharedContext
    from .models import UserProfile

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

    def _get_agent(self, name: str) -> Any:
        """Get agent instance from registry."""
        cls = self.registry.get(name)
        if not cls:
            raise ValueError(f"Agent '{name}' not found in registry")
        return cls()

    async def _call_agent_with_fault_tolerance(
        self, agent_name: str, agent: Any, method: str, *args: Any
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
            with trace_operation(
                "orchestrator", "agent_call", agent=agent_name, method=method
            ):
                fn = getattr(agent, method)

                # Execute with timeout
                if asyncio.iscoroutinefunction(fn):
                    result = await with_timeout(
                        fn(*args),
                        timeout_seconds=self.agent_timeout,
                        operation_name=operation_name,
                    )
                else:
                    result = await with_timeout(
                        asyncio.to_thread(fn, *args),
                        timeout_seconds=self.agent_timeout,
                        operation_name=operation_name,
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
                    operation_name="planner.plan_llm",
                )
                tasks = [t.model_dump() for t in tasks_result.get("tasks", [])]
                logger.info(f"Planner generated {len(tasks)} tasks")

                # publish plan.created event
                try:
                    bus = get_event_bus()
                    await bus.publish(
                        Event(
                            topic=Topics.PLAN_CREATED,
                            source="orchestrator",
                            data={"goal": goal, "task_count": len(tasks)},
                        )
                    )
                except Exception:
                    logger.debug("Failed to publish plan.created event", exc_info=True)

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
                    self.obs_logger.log_agent_handoff(
                        "orchestrator", name, {"method": method}
                    )
                    coros.append(
                        self._call_agent_with_fault_tolerance(name, inst, method, arg)
                    )
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
                "goal": goal,
            }

            # publish plan.completed event
            try:
                bus = get_event_bus()
                await bus.publish(
                    Event(
                        topic=Topics.PLAN_COMPLETED,
                        source="orchestrator",
                        data={
                            "goal": goal,
                            "successful_agents": successful_agents,
                            "failed_agents": failed_agents,
                        },
                    )
                )
            except Exception:
                logger.debug("Failed to publish plan.completed event", exc_info=True)

            return results

    async def run_with_capabilities(self, goal: str) -> Dict[str, Any]:
        """Run workflow using the capability registry instead of agents.

        This is an alternative entry point that uses capabilities directly,
        bypassing the agent layer. Useful for lighter-weight orchestration.

        Parameters
        ----------
        goal : str
            User's high-level goal.

        Returns
        -------
        Dict[str, Any]
            Dictionary containing results keyed by capability name.
        """
        with trace_operation("orchestrator", "run_with_capabilities", goal=goal):
            logger.info(f"Capability-based workflow for goal: {goal}")

            # run planning capability
            plan_cap = CAPABILITY_REGISTRY.get("plan")
            if not plan_cap:
                raise AgentError("plan capability not registered", agent_name="planner")

            try:
                tasks_result = await with_timeout(
                    plan_cap.fn({"goal": goal}),
                    timeout_seconds=self.agent_timeout,
                    operation_name="capability.plan",
                )
                tasks = [t.model_dump() for t in tasks_result.get("tasks", [])]
            except Exception as exc:
                raise AgentError(
                    f"Plan capability failed: {exc}", agent_name="planner"
                ) from exc

            # run deterministic capabilities in parallel
            deterministic = {
                "create_schedule": tasks,
                "add_wellness_nudges": tasks,
                "motivate": goal,
                "create_focus_sessions": tasks,
            }

            results: Dict[str, Any] = {"plan": tasks}
            coros = []
            cap_names: List[str] = []

            for name, arg in deterministic.items():
                cap = CAPABILITY_REGISTRY.get(name)
                if not cap:
                    continue
                cap_names.append(name)
                if asyncio.iscoroutinefunction(cap.fn):
                    coros.append(
                        with_timeout(
                            cap.fn(arg),
                            timeout_seconds=self.agent_timeout,
                            operation_name=f"capability.{name}",
                        )
                    )
                else:
                    coros.append(
                        with_timeout(
                            asyncio.to_thread(cap.fn, arg),
                            timeout_seconds=self.agent_timeout,
                            operation_name=f"capability.{name}",
                        )
                    )

            outputs = await asyncio.gather(*coros, return_exceptions=True)

            for name, value in zip(cap_names, outputs):
                if isinstance(value, Exception):
                    logger.error(f"Capability {name} failed: {value}")
                    results[name] = None
                else:
                    results[name] = value

            # backward compat
            if "create_schedule" in results:
                results["schedule"] = results["create_schedule"]

            return results

    def run_sync(self, goal: str) -> Dict[str, Any]:
        """Synchronous wrapper for the async run method."""
        return asyncio.run(self.run(goal))


class OrchestratorV2:
    """Phased orchestrator for the v0.4 collaboration protocol."""

    def __init__(self, agent_timeout: float = 30.0) -> None:
        self.registry = AGENT_REGISTRY
        self.agent_timeout = agent_timeout
        self.obs_logger = get_observability_logger()

    def _get_agent(self, name: str) -> Any:
        """Get agent instance from registry.

        Parameters
        ----------
        name : str
            The registered agent name.

        Returns
        -------
        Any
            An instantiated agent.

        Raises
        ------
        ValueError
            If the agent name is not found in the registry.
        """
        cls = self.registry.get(name)
        if not cls:
            raise ValueError(f"Agent '{name}' not found in registry")
        return cls()

    async def _run_agent(
        self, agent_name: str, agent: Any, context: "SharedContext"
    ) -> Any:
        """Run a single agent with fault tolerance.

        Parameters
        ----------
        agent_name : str
            Name of the agent (for logging and output storage).
        agent : Any
            The agent instance to run.
        context : SharedContext
            The shared workflow context.

        Returns
        -------
        Any
            The agent's output, or ``None`` if the agent failed.
        """
        try:
            with trace_operation("orchestrator_v2", "agent_run", agent=agent_name):
                result = await with_timeout(
                    agent.run(context),
                    timeout_seconds=self.agent_timeout,
                    operation_name=f"{agent_name}.run",
                )
                context.store_output(agent_name, result)
                return result
        except Exception as e:
            logger.error(f"Agent {agent_name} failed in OrchestratorV2: {e}")
            context.store_output(agent_name, None)
            return None

    async def _run_phase(
        self,
        phase_name: str,
        agent_names: List[str],
        context: "SharedContext",
    ) -> Dict[str, Any]:
        """Run a set of agents in parallel within a phase.

        Agents are filtered by ``can_contribute(context)`` before execution.
        Agents that lack the ``BaseAgent`` interface (``run`` and
        ``can_contribute``) are silently skipped for backward compatibility.

        Parameters
        ----------
        phase_name : str
            Human-readable name of the phase (for logging).
        agent_names : list[str]
            Registered names of agents to attempt.
        context : SharedContext
            The shared workflow context.

        Returns
        -------
        dict[str, Any]
            Mapping of agent name to output for agents that ran.
        """
        logger.info(
            f"OrchestratorV2 phase '{phase_name}' starting with agents: {agent_names}"
        )

        coros: List[Any] = []
        names: List[str] = []
        for name in agent_names:
            try:
                agent = self._get_agent(name)
                # check if agent supports BaseAgent interface
                if not hasattr(agent, "run") or not hasattr(agent, "can_contribute"):
                    continue
                if not agent.can_contribute(context):
                    logger.info(f"Agent {name} opted out of phase {phase_name}")
                    continue
                coros.append(self._run_agent(name, agent, context))
                names.append(name)
            except ValueError:
                continue

        if not coros:
            return {}

        outputs = await asyncio.gather(*coros, return_exceptions=True)

        results: Dict[str, Any] = {}
        for name, value in zip(names, outputs):
            if isinstance(value, Exception):
                logger.error(f"Agent {name} raised in phase {phase_name}: {value}")
                results[name] = None
            else:
                results[name] = value

        return results

    async def run(
        self,
        goal: str,
        energy_level: str = "medium",
        user_profile: "UserProfile | None" = None,
    ) -> "SharedContext":
        """Run the full 5-phase orchestration pipeline.

        Parameters
        ----------
        goal : str
            The user's goal.
        energy_level : str
            Energy level: low, medium, high.
        user_profile : UserProfile or None
            Optional user profile override.

        Returns
        -------
        SharedContext
            The completed shared context with all agent outputs.
        """
        from .collaboration.context import SharedContext
        from .models import EnergyConfig, EnergyLevel, UserProfile

        energy = EnergyLevel(energy_level)
        profile = user_profile or UserProfile()

        context = SharedContext(
            goal=goal,
            user_profile=profile,
            energy_level=energy,
            energy_config=EnergyConfig.for_level(energy),
        )

        with trace_operation("orchestrator_v2", "run", goal=goal):
            # phase 1: analysis -- planner breaks goal into tasks
            logger.info("OrchestratorV2 Phase 1: Analysis")
            await self._run_phase("analysis", ["planner"], context)

            # phase 2: assessment -- guardian checks overwhelm, chronos checks calendar
            logger.info("OrchestratorV2 Phase 2: Assessment")
            await self._run_phase("assessment", ["guardian", "chronos"], context)

            # phase 3: adaptation -- all agents read signals and adapt
            logger.info("OrchestratorV2 Phase 3: Adaptation")
            await self._run_phase(
                "adaptation",
                ["mentor", "liaison", "focusbuddy"],
                context,
            )

            # phase 4: execution -- any remaining work
            # (agents that need signals from phase 3)
            logger.info("OrchestratorV2 Phase 4: Execution")
            # no-op in base implementation; agents do their work in phases 1-3

            # phase 5: synthesis -- scribe persists
            logger.info("OrchestratorV2 Phase 5: Synthesis")
            await self._run_phase("synthesis", ["scribe"], context)

            # publish plan.completed event
            try:
                bus = get_event_bus()
                await bus.publish(
                    Event(
                        topic=Topics.PLAN_COMPLETED,
                        source="orchestrator_v2",
                        data={
                            "goal": goal,
                            "agents": list(context.agent_outputs.keys()),
                        },
                    )
                )
            except Exception:
                pass

            return context
