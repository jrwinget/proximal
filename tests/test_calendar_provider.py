"""Tests for calendar provider abstraction (WP4)."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from packages.core.integrations.calendar_provider import (
    CalendarEvent,
    GoogleCalendarProvider,
    OutlookCalendarProvider,
    StubCalendarProvider,
    get_calendar_provider,
)


@pytest.fixture
def stub():
    return StubCalendarProvider()


class TestCalendarEvent:
    def test_defaults(self):
        e = CalendarEvent(
            title="Meeting",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        assert len(e.id) == 8
        assert e.title == "Meeting"
        assert e.all_day is False


class TestStubProvider:
    async def test_create_and_get(self, stub):
        event = CalendarEvent(
            title="Test",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        await stub.create_event(event)
        events = await stub.get_events(
            datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 2, 0, 0, tzinfo=timezone.utc),
        )
        assert len(events) == 1
        assert events[0].title == "Test"

    async def test_delete(self, stub):
        event = CalendarEvent(
            title="Delete Me",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        await stub.create_event(event)
        assert await stub.delete_event(event.id) is True
        events = await stub.get_events(
            datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 2, 0, 0, tzinfo=timezone.utc),
        )
        assert len(events) == 0

    async def test_delete_nonexistent(self, stub):
        assert await stub.delete_event("nope") is False

    async def test_filter_by_range(self, stub):
        e1 = CalendarEvent(
            title="In range",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        e2 = CalendarEvent(
            title="Out of range",
            start=datetime(2025, 1, 2, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 2, 10, 0, tzinfo=timezone.utc),
        )
        await stub.create_event(e1)
        await stub.create_event(e2)

        events = await stub.get_events(
            datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 1, 23, 59, tzinfo=timezone.utc),
        )
        assert len(events) == 1
        assert events[0].title == "In range"

    async def test_update_event(self, stub):
        event = CalendarEvent(
            title="Original",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        await stub.create_event(event)
        updated = CalendarEvent(
            title="Updated",
            start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        )
        result = await stub.update_event(event.id, updated)
        assert result is not None
        assert result.title == "Updated"
        assert result.id == event.id
        # verify the change persists
        events = await stub.get_events(
            datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 2, 0, 0, tzinfo=timezone.utc),
        )
        assert len(events) == 1
        assert events[0].title == "Updated"

    async def test_update_event_nonexistent(self, stub):
        event = CalendarEvent(
            title="Ghost",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        result = await stub.update_event("nope", event)
        assert result is None

    async def test_update_event(self, stub):
        event = CalendarEvent(
            title="Original",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        await stub.create_event(event)
        updated = CalendarEvent(
            title="Updated",
            start=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 11, 0, tzinfo=timezone.utc),
        )
        result = await stub.update_event(event.id, updated)
        assert result is not None
        assert result.title == "Updated"
        assert result.id == event.id
        # verify the change persists
        events = await stub.get_events(
            datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 1, 2, 0, 0, tzinfo=timezone.utc),
        )
        assert len(events) == 1
        assert events[0].title == "Updated"

    async def test_update_event_nonexistent(self, stub):
        event = CalendarEvent(
            title="Ghost",
            start=datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc),
            end=datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )
        result = await stub.update_event("nope", event)
        assert result is None


class TestFactory:
    def test_stub_provider(self):
        p = get_calendar_provider("stub")
        assert isinstance(p, StubCalendarProvider)

    def test_unknown_falls_back(self):
        p = get_calendar_provider("unknown")
        assert isinstance(p, StubCalendarProvider)

    def test_google_provider(self):
        with patch.object(
            GoogleCalendarProvider,
            "_build_service",
            staticmethod(lambda *_a, **_k: MagicMock()),
        ):
            p = get_calendar_provider(
                "google",
                service_account_info={"type": "service_account", "project_id": "test"},
            )
        with patch.object(
            GoogleCalendarProvider,
            "_build_service",
            staticmethod(lambda *_a, **_k: MagicMock()),
        ):
            p = get_calendar_provider(
                "google",
                service_account_info={"type": "service_account", "project_id": "test"},
            )
        assert isinstance(p, GoogleCalendarProvider)


def _mock_google_modules():
    """Create mock google auth and discovery modules."""
    mock_sa = MagicMock()
    mock_creds = MagicMock()
    mock_sa.Credentials.from_service_account_info.return_value = mock_creds
    mock_sa.Credentials.from_service_account_file.return_value = mock_creds

    mock_service = MagicMock()
    mock_build = MagicMock(return_value=mock_service)

    return mock_sa, mock_build, mock_service


@pytest.fixture
def google_provider():
    """Create a GoogleCalendarProvider with mocked google dependencies."""
    _mock_sa, _mock_build, mock_service = _mock_google_modules()

    with patch.object(
        GoogleCalendarProvider,
        "_build_service",
        staticmethod(lambda *_args, **_kwargs: mock_service),
    ):
        provider = GoogleCalendarProvider(
            calendar_id="test-cal",
            service_account_info={"type": "service_account", "project_id": "test"},
        )
    return provider, mock_service


class TestGoogleCalendarProvider:
    """Tests for the GoogleCalendarProvider with mocked Google API."""

    async def test_get_events(self, google_provider):
        provider, mock_service = google_provider
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "evt1",
                    "summary": "Team Standup",
                    "description": "Daily standup",
                    "location": "Room A",
                    "start": {"dateTime": "2025-06-01T09:00:00+00:00"},
                    "end": {"dateTime": "2025-06-01T09:30:00+00:00"},
                },
                {
                    "id": "evt2",
                    "summary": "Lunch",
                    "start": {"dateTime": "2025-06-01T12:00:00+00:00"},
                    "end": {"dateTime": "2025-06-01T13:00:00+00:00"},
                },
            ]
        }

        events = await provider.get_events(
            datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 6, 2, 0, 0, tzinfo=timezone.utc),
        )

        assert len(events) == 2
        assert events[0].id == "evt1"
        assert events[0].title == "Team Standup"
        assert events[0].description == "Daily standup"
        assert events[0].location == "Room A"
        assert events[0].all_day is False
        assert events[1].id == "evt2"
        assert events[1].title == "Lunch"

    async def test_get_events_all_day(self, google_provider):
        provider, mock_service = google_provider
        mock_service.events.return_value.list.return_value.execute.return_value = {
            "items": [
                {
                    "id": "allday1",
                    "summary": "Holiday",
                    "start": {"date": "2025-06-01"},
                    "end": {"date": "2025-06-02"},
                }
            ]
        }

        events = await provider.get_events(
            datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 6, 2, 0, 0, tzinfo=timezone.utc),
        )

        assert len(events) == 1
        assert events[0].all_day is True
        assert events[0].title == "Holiday"
        assert events[0].start.year == 2025
        assert events[0].start.month == 6
        assert events[0].start.day == 1

    async def test_create_event(self, google_provider):
        provider, mock_service = google_provider
        mock_service.events.return_value.insert.return_value.execute.return_value = {
            "id": "new-evt",
            "summary": "New Meeting",
            "description": "",
            "start": {"dateTime": "2025-06-01T14:00:00+00:00"},
            "end": {"dateTime": "2025-06-01T15:00:00+00:00"},
        }

        event = CalendarEvent(
            title="New Meeting",
            start=datetime(2025, 6, 1, 14, 0, tzinfo=timezone.utc),
            end=datetime(2025, 6, 1, 15, 0, tzinfo=timezone.utc),
        )
        result = await provider.create_event(event)

        assert result.id == "new-evt"
        assert result.title == "New Meeting"
        mock_service.events.return_value.insert.assert_called_once()
        call_kwargs = mock_service.events.return_value.insert.call_args
        assert call_kwargs[1]["calendarId"] == "test-cal"
        body = call_kwargs[1]["body"]
        assert body["summary"] == "New Meeting"
        assert "dateTime" in body["start"]

    async def test_update_event(self, google_provider):
        provider, mock_service = google_provider
        mock_service.events.return_value.patch.return_value.execute.return_value = {
            "id": "evt1",
            "summary": "Updated Meeting",
            "description": "Updated desc",
            "start": {"dateTime": "2025-06-01T10:00:00+00:00"},
            "end": {"dateTime": "2025-06-01T11:00:00+00:00"},
        }

        event = CalendarEvent(
            title="Updated Meeting",
            description="Updated desc",
            start=datetime(2025, 6, 1, 10, 0, tzinfo=timezone.utc),
            end=datetime(2025, 6, 1, 11, 0, tzinfo=timezone.utc),
        )
        result = await provider.update_event("evt1", event)

        assert result is not None
        assert result.id == "evt1"
        assert result.title == "Updated Meeting"
        mock_service.events.return_value.patch.assert_called_once()
        call_kwargs = mock_service.events.return_value.patch.call_args
        assert call_kwargs[1]["calendarId"] == "test-cal"
        assert call_kwargs[1]["eventId"] == "evt1"

    async def test_delete_event(self, google_provider):
        provider, mock_service = google_provider
        mock_service.events.return_value.delete.return_value.execute.return_value = None

        result = await provider.delete_event("evt1")

        assert result is True
        mock_service.events.return_value.delete.assert_called_once()
        call_kwargs = mock_service.events.return_value.delete.call_args
        assert call_kwargs[1]["calendarId"] == "test-cal"
        assert call_kwargs[1]["eventId"] == "evt1"

    async def test_delete_event_not_found(self, google_provider):
        provider, mock_service = google_provider
        # simulate google api HttpError 404
        error = Exception("404 Not Found")
        mock_service.events.return_value.delete.return_value.execute.side_effect = error

        result = await provider.delete_event("nonexistent")

        assert result is False

    async def test_get_events_api_error(self, google_provider):
        provider, mock_service = google_provider
        mock_service.events.return_value.list.return_value.execute.side_effect = (
            Exception("API error")
        )

        events = await provider.get_events(
            datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc),
            datetime(2025, 6, 2, 0, 0, tzinfo=timezone.utc),
        )

        assert events == []

    def test_lazy_import(self):
        """Verify GoogleCalendarProvider does not import google at module level."""
        # the calendar_provider module is already imported; verify that no
        # google.* modules were pulled in as a side effect of that import.
        # google modules should only be imported inside __init__ when the
        # provider is actually instantiated.
        import inspect

        src = inspect.getsource(GoogleCalendarProvider.__init__)
        # constructor delegates to _build_service which does the lazy import
        build_src = inspect.getsource(GoogleCalendarProvider._build_service)
        assert "from google" not in src, "google import should not be in __init__"
        assert "from google" in build_src, "lazy import should be in _build_service"

        # also verify the module itself doesn't have top-level google imports
        import packages.core.integrations.calendar_provider as cp

        mod_src = inspect.getsource(cp)
        # check that there's no top-level google import (outside of class defs)
        top_lines = []
        in_class = False
        for line in mod_src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("class "):
                in_class = True
            if not in_class and ("from google" in line or "import google" in line):
                top_lines.append(line)
        assert top_lines == [], f"unexpected top-level google imports: {top_lines}"

    def test_missing_credentials_raises(self):
        """Verify ValueError when no credentials are provided."""
        mock_sa, mock_build, _mock_service = _mock_google_modules()

        with patch.dict(
            "sys.modules",
            {
                "google": MagicMock(),
                "google.oauth2": MagicMock(),
                "google.oauth2.service_account": mock_sa,
                "googleapiclient": MagicMock(),
                "googleapiclient.discovery": MagicMock(build=mock_build),
                "googleapiclient.errors": MagicMock(),
            },
        ):
            with pytest.raises(
                ValueError, match="service_account_path or service_account_info"
            ):
                GoogleCalendarProvider(calendar_id="test-cal")


# ---------------------------------------------------------------------------
# Outlook Calendar Provider tests
# ---------------------------------------------------------------------------


def _mock_msal():
    """Create a mock msal module with ConfidentialClientApplication."""
    mock_msal = MagicMock()
    mock_app = MagicMock()
    mock_app.acquire_token_for_client.return_value = {
        "access_token": "fake-token-123",
    }
    mock_msal.ConfidentialClientApplication.return_value = mock_app
    return mock_msal, mock_app


def _make_graph_event(
    event_id="evt-1",
    subject="Team Standup",
    description="Daily sync",
    is_all_day=False,
    start_dt="2025-06-01T09:00:00",
    end_dt="2025-06-01T10:00:00",
    location="Room A",
):
    """Build a Microsoft Graph API event dict."""
    return {
        "id": event_id,
        "subject": subject,
        "bodyPreview": description,
        "isAllDay": is_all_day,
        "start": {"dateTime": start_dt, "timeZone": "UTC"},
        "end": {"dateTime": end_dt, "timeZone": "UTC"},
        "location": {"displayName": location},
    }


class TestOutlookCalendarProvider:
    """Tests for OutlookCalendarProvider with mocked MSAL and httpx."""

    @pytest.fixture
    def mock_msal_module(self):
        mock_msal, mock_app = _mock_msal()
        return mock_msal, mock_app

    @pytest.fixture
    def provider(self, mock_msal_module):
        mock_msal, _ = mock_msal_module
        with patch.dict("sys.modules", {"msal": mock_msal}):
            return OutlookCalendarProvider(
                client_id="test-client-id",
                client_secret="test-secret",
                tenant_id="test-tenant",
                user_id="user@example.com",
            )

    async def test_get_events(self, provider, mock_msal_module):
        """mock token acquisition and httpx GET, verify CalendarEvent objects."""
        graph_events = [
            _make_graph_event(),
            _make_graph_event(
                event_id="evt-2",
                subject="Lunch",
                start_dt="2025-06-01T12:00:00",
                end_dt="2025-06-01T13:00:00",
            ),
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": graph_events}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            events = await provider.get_events(
                datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc),
                datetime(2025, 6, 2, 0, 0, tzinfo=timezone.utc),
            )

        assert len(events) == 2
        assert events[0].title == "Team Standup"
        assert events[0].id == "evt-1"
        assert events[1].title == "Lunch"
        assert isinstance(events[0], CalendarEvent)

    async def test_get_events_all_day(self, provider, mock_msal_module):
        """mock an all-day event, verify all_day=True."""
        graph_events = [
            _make_graph_event(
                is_all_day=True,
                subject="Holiday",
                start_dt="2025-06-01T00:00:00",
                end_dt="2025-06-02T00:00:00",
            ),
        ]
        mock_response = MagicMock()
        mock_response.json.return_value = {"value": graph_events}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            events = await provider.get_events(
                datetime(2025, 6, 1, tzinfo=timezone.utc),
                datetime(2025, 6, 2, tzinfo=timezone.utc),
            )

        assert len(events) == 1
        assert events[0].all_day is True
        assert events[0].title == "Holiday"

    async def test_create_event(self, provider, mock_msal_module):
        """mock httpx POST, verify correct body sent and CalendarEvent returned."""
        created_graph_event = _make_graph_event(event_id="new-evt")
        mock_response = MagicMock()
        mock_response.json.return_value = created_graph_event
        mock_response.raise_for_status = MagicMock()

        event = CalendarEvent(
            title="Team Standup",
            start=datetime(2025, 6, 1, 9, 0),
            end=datetime(2025, 6, 1, 10, 0),
            description="Daily sync",
            location="Room A",
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await provider.create_event(event)

            call_kwargs = mock_client.post.call_args
            body = call_kwargs.kwargs["json"]
            assert body["subject"] == "Team Standup"
            assert body["isAllDay"] is False
            assert body["start"]["timeZone"] == "UTC"

        assert isinstance(result, CalendarEvent)
        assert result.id == "new-evt"

    async def test_update_event(self, provider, mock_msal_module):
        """mock httpx PATCH, verify correct call and return."""
        updated_graph_event = _make_graph_event(
            event_id="evt-1", subject="Updated Standup"
        )
        mock_response = MagicMock()
        mock_response.json.return_value = updated_graph_event
        mock_response.raise_for_status = MagicMock()

        event = CalendarEvent(
            title="Updated Standup",
            start=datetime(2025, 6, 1, 9, 0),
            end=datetime(2025, 6, 1, 10, 0),
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.patch.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await provider.update_event("evt-1", event)

            call_args = mock_client.patch.call_args
            assert "events/evt-1" in call_args.args[0]

        assert result is not None
        assert result.title == "Updated Standup"

    async def test_delete_event(self, provider, mock_msal_module):
        """mock httpx DELETE returning 204, verify returns True."""
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.delete.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await provider.delete_event("evt-1")

        assert result is True

    async def test_delete_event_not_found(self, provider, mock_msal_module):
        """mock DELETE returning 404, verify returns False."""
        import httpx as real_httpx

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = real_httpx.HTTPStatusError(
            "Not Found",
            request=MagicMock(),
            response=mock_response,
        )

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.delete.return_value = mock_response
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await provider.delete_event("nonexistent")

        assert result is False

    async def test_auth_failure(self, provider, mock_msal_module):
        """mock MSAL returning error, verify graceful failure."""
        _, mock_app = mock_msal_module
        mock_app.acquire_token_for_client.return_value = {
            "error": "invalid_client",
            "error_description": "Client authentication failed",
        }

        events = await provider.get_events(
            datetime(2025, 6, 1, tzinfo=timezone.utc),
            datetime(2025, 6, 2, tzinfo=timezone.utc),
        )
        assert events == []

    def test_lazy_import(self):
        """verify msal is not imported at module level."""
        import inspect

        import packages.core.integrations.calendar_provider as mod

        # check that the module source has no top-level msal import
        src = inspect.getsource(mod)
        top_lines = []
        in_class = False
        for line in src.splitlines():
            stripped = line.lstrip()
            if stripped.startswith("class "):
                in_class = True
            if not in_class and ("import msal" in line or "from msal" in line):
                top_lines.append(line)
        assert top_lines == [], f"unexpected top-level msal imports: {top_lines}"


class TestLegacyCalendarRemoved:
    """Ensure the legacy calendar.py placeholder is gone."""

    def test_legacy_calendar_module_does_not_exist(self):
        # the old placeholder file should not be on disk
        from pathlib import Path

        legacy = (
            Path(__file__).resolve().parent.parent
            / "packages"
            / "core"
            / "integrations"
            / "calendar.py"
        )
        assert not legacy.exists(), "legacy calendar.py should be removed"

    def test_calendar_provider_is_canonical(self):
        # calendar_provider module should be importable as the canonical calendar integration
        from packages.core.integrations.calendar_provider import (
            CalendarProvider,
            get_calendar_provider,
        )

        assert CalendarProvider is not None
        assert callable(get_calendar_provider)
