from __future__ import annotations
from .registry import AGENT_REGISTRY as AGENT_REGISTRY, register_agent as register_agent

# ensure built-in agents are registered on import
from .planner import PlannerAgent as PlannerAgent
from .chronos import ChronosAgent as ChronosAgent
from .guardian import GuardianAgent as GuardianAgent
from .mentor import MentorAgent as MentorAgent
from .liaison import LiaisonAgent as LiaisonAgent
from .scribe import ScribeAgent as ScribeAgent
from .focusbuddy import FocusBuddyAgent as FocusBuddyAgent

from .planner import (
    _json as _json,
    clarify_llm as clarify_llm,
    integrate_clarifications_llm as integrate_clarifications_llm,
    plan_llm as plan_llm,
    prioritize_llm as prioritize_llm,
    estimate_llm as estimate_llm,
    package_llm as package_llm,
    breakdown_task_llm as breakdown_task_llm,
)
