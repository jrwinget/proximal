"""Notification provider registry and dispatch."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class NotificationPayload(BaseModel):
    """Payload for a notification."""

    title: str
    body: str
    severity: str = "info"
    source: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class NotificationProvider(ABC):
    """Abstract notification provider."""

    name: str = "base"

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> bool:
        """Send a notification. Returns True on success."""
        ...

    @property
    def is_configured(self) -> bool:
        """Whether this provider has the required configuration."""
        return False


# global registry
_providers: dict[str, NotificationProvider] = {}


def register_notification_provider(provider: NotificationProvider) -> None:
    """Register a notification provider instance."""
    _providers[provider.name] = provider


def get_notification_providers() -> dict[str, NotificationProvider]:
    """Return all registered providers."""
    return dict(_providers)


async def send_notification(payload: NotificationPayload) -> dict[str, bool]:
    """Send a notification to all configured providers.

    Parameters
    ----------
    payload : NotificationPayload
        The notification to send.

    Returns
    -------
    dict[str, bool]
        Results keyed by provider name (True = success).
    """
    results: dict[str, bool] = {}
    for name, provider in _providers.items():
        if not provider.is_configured:
            continue
        try:
            success = await provider.send(payload)
            results[name] = success
        except Exception:
            logger.exception("Notification provider %s failed", name)
            results[name] = False
    return results
