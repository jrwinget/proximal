"""Calendar provider abstraction for Chronos agent.

Provides a pluggable calendar interface with a stub implementation for
development/testing and stubs for Google/Outlook that can be filled in later.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class CalendarEvent(BaseModel):
    """A calendar event."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    title: str
    start: datetime
    end: datetime
    description: str = ""
    location: str = ""
    all_day: bool = False


class CalendarProvider(ABC):
    """Abstract calendar interface."""

    @abstractmethod
    async def get_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        """Retrieve events in a time range."""
        ...

    @abstractmethod
    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        """Create a new calendar event."""
        ...

    @abstractmethod
    async def update_event(self, event_id: str, event: CalendarEvent) -> CalendarEvent | None:
        """Update an existing calendar event.

        Parameters
        ----------
        event_id : str
            The ID of the event to update.
        event : CalendarEvent
            The updated event data.

        Returns
        -------
        CalendarEvent | None
            The updated event, or None if not found.
        """
        ...

    @abstractmethod
    async def delete_event(self, event_id: str) -> bool:
        """Delete an event by ID."""
        ...


class StubCalendarProvider(CalendarProvider):
    """In-memory calendar for development and testing."""

    def __init__(self) -> None:
        self._events: list[CalendarEvent] = []

    async def get_events(self, start: datetime, end: datetime) -> list[CalendarEvent]:
        return [e for e in self._events if e.start >= start and e.end <= end]

    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        self._events.append(event)
        return event

    async def update_event(self, event_id: str, event: CalendarEvent) -> CalendarEvent | None:
        for i, e in enumerate(self._events):
            if e.id == event_id:
                updated = event.model_copy(update={"id": event_id})
                self._events[i] = updated
                return updated
        return None

    async def delete_event(self, event_id: str) -> bool:
        before = len(self._events)
        self._events = [e for e in self._events if e.id != event_id]
        return len(self._events) < before


class GoogleCalendarProvider(CalendarProvider):
    """Google Calendar provider (requires [calendar] extra).

    Parameters
    ----------
    calendar_id : str
        Google Calendar ID (default "primary").
    service_account_path : str | None
        Path to service account JSON key file.
    service_account_info : dict | None
        Service account info dict (alternative to file path).
    """

    def __init__(
        self,
        calendar_id: str = "primary",
        service_account_path: str | None = None,
        service_account_info: dict | None = None,
    ) -> None:
        self._calendar_id = calendar_id
        self._service = self._build_service(
            service_account_path, service_account_info
        )

    @staticmethod
    def _build_service(
        service_account_path: str | None,
        service_account_info: dict | None,
    ):  # noqa: ANN205 — return type depends on google lib
        """Build the Google Calendar API service client.

        Lazy-imports google packages so the [calendar] extra is only
        required when actually instantiating this provider.
        """
        try:
            from google.oauth2 import service_account as sa
            from googleapiclient.discovery import build
        except ImportError:
            raise ImportError(
                "Google Calendar requires the [calendar] extra: "
                "pip install proximal[calendar]"
            ) from None

        scopes = ["https://www.googleapis.com/auth/calendar"]
        if service_account_info:
            creds = sa.Credentials.from_service_account_info(
                service_account_info, scopes=scopes
            )
        elif service_account_path:
            creds = sa.Credentials.from_service_account_file(
                service_account_path, scopes=scopes
            )
        else:
            raise ValueError(
                "Either service_account_path or service_account_info must be provided"
            )

        return build("calendar", "v3", credentials=creds)

    # -- public api ----------------------------------------------------------

    async def get_events(
        self, start: datetime, end: datetime
    ) -> list[CalendarEvent]:

        try:
            result = await asyncio.to_thread(
                lambda: self._service.events()
                .list(
                    calendarId=self._calendar_id,
                    timeMin=start.isoformat()
                    + ("Z" if not start.tzinfo else ""),
                    timeMax=end.isoformat()
                    + ("Z" if not end.tzinfo else ""),
                    singleEvents=True,
                    orderBy="startTime",
                )
                .execute()
            )
            return [self._to_event(item) for item in result.get("items", [])]
        except Exception:
            logger.exception("failed to fetch google calendar events")
            return []

    async def create_event(self, event: CalendarEvent) -> CalendarEvent:

        body = self._to_body(event)
        result = await asyncio.to_thread(
            lambda: self._service.events()
            .insert(calendarId=self._calendar_id, body=body)
            .execute()
        )
        return self._to_event(result)

    async def update_event(
        self, event_id: str, event: CalendarEvent
    ) -> CalendarEvent | None:

        body = self._to_body(event)
        try:
            result = await asyncio.to_thread(
                lambda: self._service.events()
                .patch(
                    calendarId=self._calendar_id,
                    eventId=event_id,
                    body=body,
                )
                .execute()
            )
            return self._to_event(result)
        except Exception:
            logger.exception(
                "failed to update google calendar event %s", event_id
            )
            return None

    async def delete_event(self, event_id: str) -> bool:

        try:
            await asyncio.to_thread(
                lambda: self._service.events()
                .delete(calendarId=self._calendar_id, eventId=event_id)
                .execute()
            )
            return True
        except Exception:
            logger.exception(
                "failed to delete google calendar event %s", event_id
            )
            return False

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _to_event(item: dict) -> CalendarEvent:
        """Convert a google api event dict to a CalendarEvent."""
        start_raw = item.get("start", {})
        end_raw = item.get("end", {})
        all_day = "date" in start_raw and "dateTime" not in start_raw
        start_str = start_raw.get("dateTime") or start_raw.get("date", "")
        end_str = end_raw.get("dateTime") or end_raw.get("date", "")
        return CalendarEvent(
            id=item.get("id", ""),
            title=item.get("summary", ""),
            start=datetime.fromisoformat(start_str),
            end=datetime.fromisoformat(end_str),
            description=item.get("description", ""),
            location=item.get("location", ""),
            all_day=all_day,
        )

    @staticmethod
    def _to_body(event: CalendarEvent) -> dict:
        """Convert a CalendarEvent to a google api event body."""
        if event.all_day:
            start = {"date": event.start.strftime("%Y-%m-%d")}
            end = {"date": event.end.strftime("%Y-%m-%d")}
        else:
            start = {"dateTime": event.start.isoformat(), "timeZone": "UTC"}
            end = {"dateTime": event.end.isoformat(), "timeZone": "UTC"}
        return {
            "summary": event.title,
            "description": event.description,
            "location": event.location,
            "start": start,
            "end": end,
        }


class OutlookCalendarProvider(CalendarProvider):
    """Outlook Calendar provider via Microsoft Graph API (requires [calendar] extra).

    Parameters
    ----------
    client_id : str
        Azure AD application client ID.
    client_secret : str
        Azure AD application client secret.
    tenant_id : str
        Azure AD tenant ID.
    user_id : str
        User email or ID whose calendar to access.
    """

    _GRAPH_BASE = "https://graph.microsoft.com/v1.0"

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        user_id: str,
    ) -> None:
        try:
            import msal
        except ImportError:
            raise ImportError(
                "Outlook Calendar requires the [calendar] extra: "
                "pip install proximal[calendar]"
            ) from None

        self._app = msal.ConfidentialClientApplication(
            client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
        )
        self._user_id = user_id
        self._base_url = f"{self._GRAPH_BASE}/users/{user_id}"

    async def _get_token(self) -> str:
        """Acquire an access token, using msal's built-in cache."""

        result = await asyncio.to_thread(
            self._app.acquire_token_for_client,
            scopes=["https://graph.microsoft.com/.default"],
        )
        if "access_token" not in result:
            raise RuntimeError(
                f"Failed to acquire Microsoft Graph token: "
                f"{result.get('error_description', 'unknown error')}"
            )
        return result["access_token"]

    def _headers(self, token: str) -> dict:
        """Build authorization headers for Graph API requests."""
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # -- public api ----------------------------------------------------------

    async def get_events(
        self, start: datetime, end: datetime
    ) -> list[CalendarEvent]:
        import httpx

        try:
            token = await self._get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._base_url}/calendarView",
                    headers=self._headers(token),
                    params={
                        "startDateTime": start.isoformat()
                        + ("Z" if not start.tzinfo else ""),
                        "endDateTime": end.isoformat()
                        + ("Z" if not end.tzinfo else ""),
                    },
                )
                resp.raise_for_status()
                return [
                    self._to_event(item)
                    for item in resp.json().get("value", [])
                ]
        except Exception:
            logger.exception("failed to fetch outlook calendar events")
            return []

    async def create_event(self, event: CalendarEvent) -> CalendarEvent:
        import httpx

        token = await self._get_token()
        body = self._to_body(event)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/events",
                headers=self._headers(token),
                json=body,
            )
            resp.raise_for_status()
            return self._to_event(resp.json())

    async def update_event(
        self, event_id: str, event: CalendarEvent
    ) -> CalendarEvent | None:
        import httpx

        try:
            token = await self._get_token()
            body = self._to_body(event)
            async with httpx.AsyncClient() as client:
                resp = await client.patch(
                    f"{self._base_url}/events/{event_id}",
                    headers=self._headers(token),
                    json=body,
                )
                resp.raise_for_status()
                return self._to_event(resp.json())
        except Exception:
            logger.exception(
                "failed to update outlook calendar event %s", event_id
            )
            return None

    async def delete_event(self, event_id: str) -> bool:
        import httpx

        try:
            token = await self._get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.delete(
                    f"{self._base_url}/events/{event_id}",
                    headers=self._headers(token),
                )
                resp.raise_for_status()
                return True
        except Exception:
            logger.exception(
                "failed to delete outlook calendar event %s", event_id
            )
            return False

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _to_event(item: dict) -> CalendarEvent:
        """convert graph api event dict to CalendarEvent"""
        return CalendarEvent(
            id=item.get("id", ""),
            title=item.get("subject", ""),
            start=datetime.fromisoformat(item["start"]["dateTime"]),
            end=datetime.fromisoformat(item["end"]["dateTime"]),
            description=item.get("bodyPreview", ""),
            location=item.get("location", {}).get("displayName", ""),
            all_day=item.get("isAllDay", False),
        )

    @staticmethod
    def _to_body(event: CalendarEvent) -> dict:
        """convert CalendarEvent to graph api event body"""
        return {
            "subject": event.title,
            "body": {"contentType": "text", "content": event.description},
            "start": {"dateTime": event.start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": event.end.isoformat(), "timeZone": "UTC"},
            "location": {"displayName": event.location},
            "isAllDay": event.all_day,
        }


def get_calendar_provider(
    provider_name: str = "stub", **kwargs: object
) -> CalendarProvider:
    """Factory for calendar providers.

    Parameters
    ----------
    provider_name : str
        One of "stub", "google", "outlook".
    **kwargs
        Extra keyword arguments forwarded to the provider constructor
        (e.g. ``calendar_id``, ``service_account_info`` for Google).

    Returns
    -------
    CalendarProvider
        The configured calendar provider instance.
    """
    if provider_name == "google":
        from packages.core.settings import get_settings

        settings = get_settings()
        return GoogleCalendarProvider(
            calendar_id=kwargs.get("calendar_id", settings.google_calendar_id),
            service_account_path=kwargs.get(
                "service_account_path", settings.google_service_account_json
            ),
            service_account_info=kwargs.get("service_account_info"),
        )

    if provider_name == "outlook":
        from packages.core.settings import get_settings

        settings = get_settings()
        return OutlookCalendarProvider(
            client_id=kwargs.get("client_id", settings.outlook_client_id or ""),
            client_secret=kwargs.get(
                "client_secret", settings.outlook_client_secret or ""
            ),
            tenant_id=kwargs.get("tenant_id", settings.outlook_tenant_id or ""),
            user_id=kwargs.get("user_id", settings.outlook_user_id or ""),
        )

    if provider_name == "stub":
        return StubCalendarProvider()

    logger.warning(
        "Unknown calendar provider '%s', falling back to stub", provider_name
    )
    return StubCalendarProvider()
