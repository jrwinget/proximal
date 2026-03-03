"""Workflow scheduler using asyncio for cron-like and event-based triggers."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from ..events import get_event_bus
from .builtins import BUILTIN_WORKFLOWS
from .definition import TriggerType, WorkflowDefinition
from .executor import WorkflowExecutor, WorkflowExecution

logger = logging.getLogger(__name__)


class WorkflowScheduler:
    """Schedule and manage workflow execution.

    Cron-like triggers use asyncio.sleep loops. Event-based triggers
    subscribe to the event bus.
    """

    def __init__(self, executor: WorkflowExecutor | None = None) -> None:
        self._executor = executor or WorkflowExecutor()
        self._workflows: dict[str, WorkflowDefinition] = dict(BUILTIN_WORKFLOWS)
        self._tasks: dict[str, asyncio.Task] = {}
        self._run_counts: dict[str, int] = {}
        self._history: list[WorkflowExecution] = []
        self._running = False

    @property
    def workflows(self) -> dict[str, WorkflowDefinition]:
        return dict(self._workflows)

    @property
    def history(self) -> list[WorkflowExecution]:
        return list(self._history)

    def register(self, workflow: WorkflowDefinition) -> None:
        """Register a workflow definition."""
        self._workflows[workflow.name] = workflow

    def start(self) -> None:
        """Start all enabled workflows."""
        if self._running:
            return
        self._running = True
        self._run_counts.clear()

        for name, wf in self._workflows.items():
            if not wf.enabled:
                continue
            if wf.trigger.trigger_type == TriggerType.cron:
                self._tasks[name] = asyncio.ensure_future(self._cron_loop(wf))
            elif wf.trigger.trigger_type == TriggerType.event:
                self._wire_event_trigger(wf)

        logger.info("WorkflowScheduler started with %d workflows", len(self._tasks))

    async def stop(self) -> None:
        """Stop all running workflows."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()

    async def run_once(self, workflow_name: str) -> WorkflowExecution | None:
        """Manually trigger a single workflow run.

        Parameters
        ----------
        workflow_name : str
            Name of the workflow to run.

        Returns
        -------
        WorkflowExecution or None
            The execution result, or None if workflow not found.
        """
        wf = self._workflows.get(workflow_name)
        if wf is None:
            return None

        return await self._execute_with_cap(wf)

    async def _execute_with_cap(self, wf: WorkflowDefinition) -> WorkflowExecution:
        """Execute workflow with daily run cap."""
        today = datetime.now(timezone.utc).date().isoformat()
        key = f"{wf.name}:{today}"
        count = self._run_counts.get(key, 0)

        if count >= wf.max_auto_runs_per_day:
            logger.warning(
                "Workflow '%s' hit daily cap (%d)", wf.name, wf.max_auto_runs_per_day
            )
            execution = WorkflowExecution(wf)
            execution.status = "skipped"
            execution.error = "Daily run cap reached"
            return execution

        execution = await self._executor.execute(wf)
        self._run_counts[key] = count + 1
        self._history.append(execution)
        return execution

    async def _cron_loop(self, wf: WorkflowDefinition) -> None:
        """Simple cron loop using asyncio.sleep."""
        try:
            while self._running:
                seconds = _seconds_until_next(wf.trigger.cron_expression)
                await asyncio.sleep(min(seconds, 60))  # check every 60s at most

                if not self._running:
                    break

                if _should_run_now(wf.trigger.cron_expression):
                    await self._execute_with_cap(wf)
                    # sleep at least 61s to avoid re-triggering same minute
                    await asyncio.sleep(61)
        except asyncio.CancelledError:
            pass

    def _wire_event_trigger(self, wf: WorkflowDefinition) -> None:
        """Subscribe to event bus for event-triggered workflows."""
        bus = get_event_bus()

        async def handler(event):
            if self._running:
                await self._execute_with_cap(wf)

        bus.subscribe(wf.trigger.event_topic, handler)


def _seconds_until_next(cron_expr: str) -> float:
    """Estimate seconds until next cron trigger (simplified)."""
    # simplified: just return 60 for polling
    return 60.0


def _should_run_now(cron_expr: str) -> bool:
    """Check if the cron expression matches the current minute (simplified).

    Supports basic format: "minute hour * * day_of_week"
    """
    parts = cron_expr.split()
    if len(parts) != 5:
        return False

    now = datetime.now(timezone.utc)

    minute, hour, dom, month, dow = parts

    if minute != "*" and int(minute) != now.minute:
        return False
    if hour != "*" and int(hour) != now.hour:
        return False
    if dow != "*":
        # support ranges like "1-5"
        if "-" in dow:
            low, high = dow.split("-")
            if not (int(low) <= now.weekday() + 1 <= int(high)):
                return False
        elif int(dow) != now.weekday() + 1:
            return False

    return True
