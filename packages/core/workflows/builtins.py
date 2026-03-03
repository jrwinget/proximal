"""Built-in workflow definitions."""

from __future__ import annotations

from .definition import (
    CheckpointPolicy,
    TriggerType,
    WorkflowDefinition,
    WorkflowStep,
    WorkflowTrigger,
)

DAILY_PLANNING = WorkflowDefinition(
    name="daily_planning",
    description="Generate tomorrow's schedule and check burnout risk",
    trigger=WorkflowTrigger(
        trigger_type=TriggerType.cron, cron_expression="0 17 * * 1-5"
    ),
    steps=[
        WorkflowStep(
            name="generate_schedule", agent="chronos", method="create_schedule"
        ),
        WorkflowStep(name="check_burnout", agent="guardian", method="add_nudges"),
        WorkflowStep(name="persist", agent="scribe", method="record_plan"),
    ],
    max_auto_runs_per_day=1,
)

PROACTIVE_CHECKIN = WorkflowDefinition(
    name="proactive_checkin",
    description="Send a wellness reminder when breaks are overdue",
    trigger=WorkflowTrigger(
        trigger_type=TriggerType.event, event_topic="guardian.nudge"
    ),
    steps=[
        WorkflowStep(name="compose_reminder", agent="guardian", method="add_nudges"),
    ],
    max_auto_runs_per_day=5,
)

WEEKLY_STATUS = WorkflowDefinition(
    name="weekly_status",
    description="Gather weekly completions and draft a status message",
    trigger=WorkflowTrigger(
        trigger_type=TriggerType.cron, cron_expression="0 16 * * 5"
    ),
    steps=[
        WorkflowStep(name="gather_completions", agent="scribe", method="record_plan"),
        WorkflowStep(
            name="draft_status",
            agent="liaison",
            method="draft_message",
            checkpoint=CheckpointPolicy.before_send,
        ),
    ],
    max_auto_runs_per_day=1,
)

ADAPTIVE_LEARNING = WorkflowDefinition(
    name="adaptive_learning",
    description="Analyse patterns and update user profile",
    trigger=WorkflowTrigger(
        trigger_type=TriggerType.cron, cron_expression="0 18 * * 0"
    ),
    steps=[
        WorkflowStep(name="analyse_patterns", agent="scribe", method="record_plan"),
    ],
    max_auto_runs_per_day=1,
)

BUILTIN_WORKFLOWS: dict[str, WorkflowDefinition] = {
    "daily_planning": DAILY_PLANNING,
    "proactive_checkin": PROACTIVE_CHECKIN,
    "weekly_status": WEEKLY_STATUS,
    "adaptive_learning": ADAPTIVE_LEARNING,
}
