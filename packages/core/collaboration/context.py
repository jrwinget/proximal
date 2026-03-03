"""Shared context for intra-workflow agent coordination.

The ``SharedContext`` carries all the state that agents within a single
orchestration run need to read and write to.  Separate from the
``EventBus`` which handles inter-workflow / reactive communication.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from ..models import EnergyConfig, EnergyLevel, UserProfile


class SharedContext(BaseModel):
    """Shared state passed through orchestration phases.

    Parameters
    ----------
    session_id : str
        Auto-generated session identifier.
    user_profile : UserProfile
        The active user profile for personalisation.
    energy_level : EnergyLevel
        Current energy level for adaptive planning.
    energy_config : EnergyConfig
        Derived energy configuration.
    goal : str
        The user's original goal text.
    tasks : list[dict]
        Tasks produced by the planner.
    signals : dict[str, Any]
        Flat dict for intra-workflow communication between agents
        (e.g. ``{"overwhelm_detected": True, "low_energy_mode": True}``).
    agent_outputs : dict[str, Any]
        Stores each agent's result keyed by agent name.
    created_at : datetime
        When this context was created.
    """

    session_id: str = Field(default_factory=lambda: uuid4().hex[:8])
    user_profile: UserProfile = Field(default_factory=UserProfile)
    energy_level: EnergyLevel = EnergyLevel.medium
    energy_config: EnergyConfig = Field(
        default_factory=lambda: EnergyConfig.for_level(EnergyLevel.medium)
    )
    goal: str = ""
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    signals: dict[str, Any] = Field(default_factory=dict)
    agent_outputs: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def set_signal(self, key: str, value: Any) -> None:
        """Set a signal for other agents to read.

        Parameters
        ----------
        key : str
            Signal name (e.g. "overwhelm_detected").
        value : Any
            Signal value.
        """
        self.signals[key] = value

    def get_signal(self, key: str, default: Any = None) -> Any:
        """Read a signal set by another agent.

        Parameters
        ----------
        key : str
            Signal name.
        default : Any
            Value to return if signal not set.

        Returns
        -------
        Any
            The signal value or default.
        """
        return self.signals.get(key, default)

    def store_output(self, agent_name: str, output: Any) -> None:
        """Store an agent's output.

        Parameters
        ----------
        agent_name : str
            Name of the agent.
        output : Any
            The agent's result.
        """
        self.agent_outputs[agent_name] = output
