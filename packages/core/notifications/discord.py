"""Discord webhook notification provider."""

from __future__ import annotations

import logging
import os

from .registry import NotificationPayload, NotificationProvider

logger = logging.getLogger(__name__)


class DiscordNotifier(NotificationProvider):
    """Send notifications via Discord webhook."""

    name = "discord"

    def __init__(self, webhook_url: str | None = None) -> None:
        self._webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")

    @property
    def is_configured(self) -> bool:
        return bool(self._webhook_url)

    async def send(self, payload: NotificationPayload) -> bool:
        """Post a message to Discord via webhook."""
        import httpx

        discord_payload = {
            "content": f"**{payload.title}**\n{payload.body}",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                self._webhook_url,
                json=discord_payload,
                timeout=10.0,
            )
            response.raise_for_status()

        return True
