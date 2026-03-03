"""Slack webhook notification provider."""

from __future__ import annotations

import logging
import os

from .registry import NotificationPayload, NotificationProvider

logger = logging.getLogger(__name__)


class SlackNotifier(NotificationProvider):
    """Send notifications via Slack incoming webhook."""

    name = "slack"

    def __init__(self, webhook_url: str | None = None) -> None:
        self._webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")

    @property
    def is_configured(self) -> bool:
        return bool(self._webhook_url)

    async def send(self, payload: NotificationPayload) -> bool:
        """Post a message to Slack via webhook."""
        import httpx

        severity_emoji = {
            "info": ":information_source:",
            "warning": ":warning:",
            "error": ":rotating_light:",
            "success": ":white_check_mark:",
        }
        emoji = severity_emoji.get(payload.severity, ":bell:")

        slack_payload = {
            "text": f"{emoji} *{payload.title}*\n{payload.body}",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._webhook_url,
                json=slack_payload,
                timeout=10.0,
            )
            response.raise_for_status()

        return True
