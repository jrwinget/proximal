"""Analytics module — task completion tracking, focus sessions, and energy patterns."""

from .aggregator import (
    AnalyticsAggregator,
    record_energy_snapshot,
    record_focus_session,
    record_task_completion,
)
from .models import EnergySnapshot, FocusSessionRecord, TaskCompletion

__all__ = [
    "AnalyticsAggregator",
    "EnergySnapshot",
    "FocusSessionRecord",
    "TaskCompletion",
    "record_energy_snapshot",
    "record_focus_session",
    "record_task_completion",
]
