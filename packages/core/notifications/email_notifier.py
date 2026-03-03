"""SMTP email notification provider."""

from __future__ import annotations

import logging
import os
import smtplib
from email.mime.text import MIMEText

from .registry import NotificationPayload, NotificationProvider

logger = logging.getLogger(__name__)


class EmailNotifier(NotificationProvider):
    """Send notifications via SMTP email."""

    name = "email"

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        from_addr: str | None = None,
        to_addr: str | None = None,
    ) -> None:
        self._host = smtp_host or os.getenv("SMTP_HOST", "")
        self._port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self._user = smtp_user or os.getenv("SMTP_USER", "")
        self._password = smtp_password or os.getenv("SMTP_PASSWORD", "")
        self._from = from_addr or os.getenv("SMTP_FROM", "")
        self._to = to_addr or os.getenv("NOTIFICATION_EMAIL_TO", "")

    @property
    def is_configured(self) -> bool:
        return bool(self._host and self._to)

    async def send(self, payload: NotificationPayload) -> bool:
        """Send an email notification via SMTP."""
        msg = MIMEText(payload.body)
        msg["Subject"] = f"[Proximal] {payload.title}"
        msg["From"] = self._from or self._user
        msg["To"] = self._to

        try:
            with smtplib.SMTP(self._host, self._port, timeout=10) as server:
                if self._user and self._password:
                    server.starttls()
                    server.login(self._user, self._password)
                server.send_message(msg)
            return True
        except Exception:
            logger.exception("Failed to send email notification")
            return False
