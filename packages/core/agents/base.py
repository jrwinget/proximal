"""Base agent class for the v0.4 collaboration protocol.

All agents extend ``BaseAgent`` and implement ``run(context)`` for phased
orchestration, while keeping their legacy methods for backward compatibility.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..collaboration.context import SharedContext
from ..events import Event


class BaseAgent(ABC):
    """Abstract base agent with collaboration support.

    Subclasses must implement:
    - ``run(context)`` — main entry point for phased orchestration
    - ``can_contribute(context)`` — whether this agent should run in the current context
    """

    name: str = "base"

    @abstractmethod
    async def run(self, context: SharedContext) -> Any:
        """Execute the agent's main logic within a shared context.

        Parameters
        ----------
        context : SharedContext
            The shared workflow context.

        Returns
        -------
        Any
            The agent's output (also stored in ``context.agent_outputs``).
        """
        ...

    def can_contribute(self, context: SharedContext) -> bool:
        """Determine whether this agent should participate in the current workflow.

        Override to implement conditional activation (e.g. Liaison only runs
        when ``deadline_at_risk`` signal is set).

        Parameters
        ----------
        context : SharedContext
            The shared workflow context.

        Returns
        -------
        bool
            True if the agent should run.
        """
        return True

    async def on_event(self, event: Event) -> None:
        """Handle a reactive event from the event bus.

        Override in agents that need reactive behaviour.

        Parameters
        ----------
        event : Event
            The event to handle.
        """
        pass
