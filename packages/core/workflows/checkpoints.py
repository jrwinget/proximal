"""Human-in-the-loop approval gates for workflow steps."""

from __future__ import annotations

import asyncio
import logging

from .definition import WorkflowStep

logger = logging.getLogger(__name__)


class CheckpointManager:
    """Manage human approval checkpoints for workflow steps.

    In CLI mode, blocks until the user approves or denies.
    In API mode, stores pending approvals for later resolution.
    """

    def __init__(self) -> None:
        self._pending: dict[str, asyncio.Future] = {}
        self._auto_approve: bool = False

    @property
    def pending_approvals(self) -> list[str]:
        """Return names of steps awaiting approval."""
        return list(self._pending.keys())

    def set_auto_approve(self, auto: bool) -> None:
        """Toggle automatic approval (for testing or trusted workflows)."""
        self._auto_approve = auto

    async def request_approval(self, step: WorkflowStep) -> bool:
        """Request human approval for a workflow step.

        Parameters
        ----------
        step : WorkflowStep
            The step requiring approval.

        Returns
        -------
        bool
            True if approved, False if denied.
        """
        if self._auto_approve:
            return True

        logger.info("Checkpoint: step '%s' awaiting approval", step.name)

        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._pending[step.name] = future

        try:
            return await future
        finally:
            self._pending.pop(step.name, None)

    def approve(self, step_name: str) -> bool:
        """Approve a pending checkpoint.

        Parameters
        ----------
        step_name : str
            Name of the step to approve.

        Returns
        -------
        bool
            True if the step was pending and is now approved.
        """
        future = self._pending.get(step_name)
        if future and not future.done():
            future.set_result(True)
            return True
        return False

    def deny(self, step_name: str) -> bool:
        """Deny a pending checkpoint.

        Parameters
        ----------
        step_name : str
            Name of the step to deny.

        Returns
        -------
        bool
            True if the step was pending and is now denied.
        """
        future = self._pending.get(step_name)
        if future and not future.done():
            future.set_result(False)
            return True
        return False
