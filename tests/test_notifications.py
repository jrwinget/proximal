"""Tests for notification system (WP5)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.events import Event, EventBus, Topics
from packages.core.notifications.discord import DiscordNotifier
from packages.core.notifications.email_notifier import EmailNotifier
from packages.core.notifications.registry import (
    NotificationPayload,
    NotificationProvider,
    _providers,
    register_notification_provider,
    send_notification,
)
from packages.core.notifications.slack import SlackNotifier
from packages.core.notifications.subscribers import register_notification_subscriptions


@pytest.fixture(autouse=True)
def _clean_providers():
    """Clear the provider registry between tests."""
    _providers.clear()
    yield
    _providers.clear()


class TestNotificationPayload:
    def test_defaults(self):
        p = NotificationPayload(title="Test", body="Hello")
        assert p.severity == "info"
        assert p.data == {}

    def test_custom(self):
        p = NotificationPayload(
            title="Alert",
            body="Something happened",
            severity="warning",
            source="guardian",
        )
        assert p.severity == "warning"


class TestRegistry:
    async def test_register_and_send(self):
        mock_provider = MagicMock(spec=NotificationProvider)
        mock_provider.name = "test"
        mock_provider.is_configured = True
        mock_provider.send = AsyncMock(return_value=True)

        register_notification_provider(mock_provider)

        payload = NotificationPayload(title="Test", body="Hello")
        results = await send_notification(payload)

        assert results["test"] is True
        mock_provider.send.assert_called_once_with(payload)

    async def test_unconfigured_skipped(self):
        mock_provider = MagicMock(spec=NotificationProvider)
        mock_provider.name = "test"
        mock_provider.is_configured = False
        mock_provider.send = AsyncMock()

        register_notification_provider(mock_provider)

        payload = NotificationPayload(title="Test", body="Hello")
        results = await send_notification(payload)

        assert results == {}
        mock_provider.send.assert_not_called()

    async def test_provider_failure_graceful(self):
        mock_provider = MagicMock(spec=NotificationProvider)
        mock_provider.name = "test"
        mock_provider.is_configured = True
        mock_provider.send = AsyncMock(side_effect=RuntimeError("boom"))

        register_notification_provider(mock_provider)

        payload = NotificationPayload(title="Test", body="Hello")
        results = await send_notification(payload)

        assert results["test"] is False


class TestSlackNotifier:
    def test_not_configured_without_url(self):
        s = SlackNotifier(webhook_url="")
        assert s.is_configured is False

    def test_configured_with_url(self):
        s = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        assert s.is_configured is True

    @patch("httpx.AsyncClient")
    async def test_send(self, mock_client_cls):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        s = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        result = await s.send(NotificationPayload(title="Hi", body="World"))

        assert result is True
        mock_client.post.assert_called_once()


class TestDiscordNotifier:
    def test_not_configured_without_url(self):
        d = DiscordNotifier(webhook_url="")
        assert d.is_configured is False

    def test_configured_with_url(self):
        d = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test")
        assert d.is_configured is True


class TestEmailNotifier:
    def test_not_configured_without_host(self):
        e = EmailNotifier(smtp_host="", to_addr="")
        assert e.is_configured is False

    def test_configured(self):
        e = EmailNotifier(smtp_host="smtp.test.com", to_addr="test@test.com")
        assert e.is_configured is True

    @patch("smtplib.SMTP")
    async def test_send(self, mock_smtp_cls):
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_server)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        e = EmailNotifier(
            smtp_host="smtp.test.com",
            smtp_port=587,
            to_addr="test@test.com",
        )
        result = await e.send(NotificationPayload(title="Hi", body="World"))
        assert result is True

    @patch("smtplib.SMTP", side_effect=ConnectionRefusedError("no server"))
    async def test_send_failure(self, mock_smtp_cls):
        e = EmailNotifier(
            smtp_host="smtp.test.com",
            to_addr="test@test.com",
        )
        result = await e.send(NotificationPayload(title="Hi", body="World"))
        assert result is False


class TestSubscribers:
    def test_register_subscriptions(self):
        bus = EventBus()
        register_notification_subscriptions(bus)

        assert Topics.PLAN_COMPLETED in bus._handlers
        assert Topics.GUARDIAN_BURNOUT_WARNING in bus._handlers
        assert Topics.GUARDIAN_ESCALATION in bus._handlers
        assert Topics.CHRONOS_CONFLICT in bus._handlers

    @patch(
        "packages.core.notifications.subscribers.send_notification",
        new_callable=AsyncMock,
    )
    async def test_plan_completed_triggers_notification(self, mock_send):
        mock_send.return_value = {}
        bus = EventBus()
        register_notification_subscriptions(bus)

        await bus.publish(
            Event(
                topic=Topics.PLAN_COMPLETED,
                source="orchestrator",
                data={"goal": "test", "successful_agents": 5},
            )
        )

        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        assert payload.title == "Plan Completed"
