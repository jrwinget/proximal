"""Reactive layer startup — wires event bus, agents, and notifications.

Call ``init_reactive_layer()`` once during application startup to activate
the v0.3 reactive features (Guardian monitoring, Chronos schedule awareness,
notification delivery).
"""

from __future__ import annotations

import logging

from .events import EventBus, get_event_bus

logger = logging.getLogger(__name__)

_initialized: bool = False


def init_reactive_layer() -> EventBus:
    """Initialize and start the reactive event system.

    Idempotent — safe to call multiple times; only the first call
    performs actual wiring.

    Returns
    -------
    EventBus
        The started global event bus.
    """
    global _initialized
    if _initialized:
        return get_event_bus()

    bus = get_event_bus()

    # wire Guardian subscriptions
    try:
        from .agents.guardian import GuardianAgent

        guardian = GuardianAgent()
        guardian.register_subscriptions(bus)
        logger.info("Guardian reactive subscriptions registered")
    except Exception:
        logger.debug("Failed to register Guardian subscriptions", exc_info=True)

    # wire Chronos subscriptions
    try:
        from .agents.chronos import ChronosAgent

        chronos = ChronosAgent()
        chronos.register_subscriptions(bus)
        logger.info("Chronos reactive subscriptions registered")
    except Exception:
        logger.debug("Failed to register Chronos subscriptions", exc_info=True)

    # wire FocusBuddy subscriptions
    try:
        from .agents.focusbuddy import FocusBuddyAgent

        focusbuddy = FocusBuddyAgent()
        focusbuddy.register_subscriptions(bus)
        logger.info("FocusBuddy reactive subscriptions registered")
    except Exception:
        logger.debug(
            "Failed to register FocusBuddy subscriptions",
            exc_info=True,
        )

    # wire notification subscriptions
    try:
        from .notifications.subscribers import register_notification_subscriptions

        _setup_notification_providers()
        register_notification_subscriptions(bus)
        logger.info("Notification subscriptions registered")
    except Exception:
        logger.debug("Failed to register notification subscriptions", exc_info=True)

    # start background dispatch loop
    try:
        bus.start()
        logger.info("Event bus started")
    except Exception:
        logger.debug("Event bus start failed (no running loop?)", exc_info=True)

    _initialized = True
    return bus


def _setup_notification_providers() -> None:
    """Register notification providers based on environment configuration."""
    from .notifications.registry import register_notification_provider

    try:
        from .notifications.slack import SlackNotifier

        slack = SlackNotifier()
        if slack.is_configured:
            register_notification_provider(slack)
            logger.info("Slack notification provider registered")
    except Exception:
        pass

    try:
        from .notifications.discord import DiscordNotifier

        discord = DiscordNotifier()
        if discord.is_configured:
            register_notification_provider(discord)
            logger.info("Discord notification provider registered")
    except Exception:
        pass

    try:
        from .notifications.email_notifier import EmailNotifier

        email = EmailNotifier()
        if email.is_configured:
            register_notification_provider(email)
            logger.info("Email notification provider registered")
    except Exception:
        pass


def reset_reactive_layer() -> None:
    """Reset the reactive layer (primarily for testing)."""
    global _initialized
    _initialized = False
