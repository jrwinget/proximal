"""Wire event bus topics to notification providers."""

from __future__ import annotations

import logging

from ..events import Event, EventBus, Topics
from .registry import NotificationPayload, send_notification

logger = logging.getLogger(__name__)


async def _on_plan_completed(event: Event) -> None:
    """Notify when a plan is completed."""
    goal = event.data.get("goal", "Unknown goal")
    agents = event.data.get("successful_agents", 0)
    await send_notification(
        NotificationPayload(
            title="Plan Completed",
            body=f"Plan for '{goal}' completed with {agents} agents.",
            severity="success",
            source="orchestrator",
            data=event.data,
        )
    )


async def _on_burnout_warning(event: Event) -> None:
    """Notify on burnout warnings."""
    await send_notification(
        NotificationPayload(
            title="Burnout Warning",
            body="Guardian has detected burnout risk patterns. Please take care of yourself.",
            severity="warning",
            source="guardian",
            data=event.data,
        )
    )


async def _on_guardian_escalation(event: Event) -> None:
    """Notify on escalated wellness warnings."""
    message = event.data.get("message", "Wellness escalation triggered.")
    await send_notification(
        NotificationPayload(
            title="Wellness Alert",
            body=message,
            severity="warning",
            source="guardian",
            data=event.data,
        )
    )


async def _on_chronos_conflict(event: Event) -> None:
    """Notify on schedule conflicts."""
    await send_notification(
        NotificationPayload(
            title="Schedule Conflict",
            body="Chronos detected a scheduling conflict with your calendar.",
            severity="warning",
            source="chronos",
            data=event.data,
        )
    )


def register_notification_subscriptions(bus: EventBus) -> None:
    """Wire default event-to-notification subscriptions.

    Parameters
    ----------
    bus : EventBus
        The event bus to subscribe to.
    """
    bus.subscribe(Topics.PLAN_COMPLETED, _on_plan_completed)
    bus.subscribe(Topics.GUARDIAN_BURNOUT_WARNING, _on_burnout_warning)
    bus.subscribe(Topics.GUARDIAN_ESCALATION, _on_guardian_escalation)
    bus.subscribe(Topics.CHRONOS_CONFLICT, _on_chronos_conflict)
