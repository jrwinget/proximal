"""Workflow definition models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class TriggerType(StrEnum):
    cron = "cron"
    event = "event"
    manual = "manual"


class WorkflowTrigger(BaseModel):
    trigger_type: TriggerType = TriggerType.manual
    cron_expression: str = ""
    event_topic: str = ""


class CheckpointPolicy(StrEnum):
    none = "none"
    before_send = "before_send"
    before_external = "before_external"
    every_step = "every_step"


class WorkflowStep(BaseModel):
    name: str
    agent: str
    method: str = "run"
    args: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: float = 30.0
    checkpoint: CheckpointPolicy = CheckpointPolicy.none


class WorkflowDefinition(BaseModel):
    name: str
    description: str = ""
    trigger: WorkflowTrigger = Field(default_factory=WorkflowTrigger)
    steps: list[WorkflowStep] = Field(default_factory=list)
    max_auto_runs_per_day: int = 10
    enabled: bool = True
