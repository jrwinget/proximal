"""Workflow step executor with fault tolerance."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..agents import AGENT_REGISTRY
from ..fault_tolerance import with_timeout
from .definition import CheckpointPolicy, WorkflowDefinition, WorkflowStep

logger = logging.getLogger(__name__)


class WorkflowExecution:
    """Tracks the state of a single workflow run."""

    def __init__(self, workflow: WorkflowDefinition) -> None:
        self.workflow = workflow
        self.status: str = "pending"
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.step_results: dict[str, Any] = {}
        self.error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_name": self.workflow.name,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "step_results": {k: str(v) for k, v in self.step_results.items()},
            "error": self.error,
        }


class WorkflowExecutor:
    """Execute workflow steps sequentially with fault tolerance."""

    def __init__(self, approval_callback=None) -> None:
        self._approval_callback = approval_callback

    async def execute(self, workflow: WorkflowDefinition) -> WorkflowExecution:
        """Run all steps in a workflow definition.

        Parameters
        ----------
        workflow : WorkflowDefinition
            The workflow to execute.

        Returns
        -------
        WorkflowExecution
            The completed execution record.
        """
        execution = WorkflowExecution(workflow)
        execution.status = "running"
        execution.started_at = datetime.now(timezone.utc)

        try:
            for step in workflow.steps:
                # checkpoint gate
                if step.checkpoint != CheckpointPolicy.none and self._approval_callback:
                    approved = await self._approval_callback(step)
                    if not approved:
                        execution.status = "paused"
                        execution.error = f"Step '{step.name}' awaiting approval"
                        return execution

                result = await self._execute_step(step)
                execution.step_results[step.name] = result

            execution.status = "completed"
        except Exception as e:
            execution.status = "failed"
            execution.error = str(e)
            logger.error("Workflow '%s' failed: %s", workflow.name, e)
        finally:
            execution.completed_at = datetime.now(timezone.utc)

        return execution

    async def _execute_step(self, step: WorkflowStep) -> Any:
        """Execute a single workflow step."""
        agent_cls = AGENT_REGISTRY.get(step.agent)
        if agent_cls is None:
            raise ValueError(f"Agent '{step.agent}' not found for step '{step.name}'")

        agent = agent_cls()
        method = getattr(agent, step.method, None)
        if method is None:
            raise ValueError(
                f"Agent '{step.agent}' has no method '{step.method}' "
                f"for step '{step.name}'"
            )

        if asyncio.iscoroutinefunction(method):
            result = await with_timeout(
                method(**step.args) if step.args else method([]),
                timeout_seconds=step.timeout_seconds,
                operation_name=f"workflow.{step.name}",
            )
        else:
            result = await with_timeout(
                asyncio.to_thread(method, **step.args)
                if step.args
                else asyncio.to_thread(method, []),
                timeout_seconds=step.timeout_seconds,
                operation_name=f"workflow.{step.name}",
            )

        return result
