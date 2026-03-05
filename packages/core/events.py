"""Event bus for inter-agent reactive communication.

Provides a pub/sub event system with wildcard topic matching, a background
async dispatch loop, and a ring buffer for debugging recent events.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from fnmatch import fnmatch
from typing import Any, Callable, Coroutine, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# standard topic vocabulary
# ---------------------------------------------------------------------------


class Topics:
    """Standard event topic constants."""

    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    SESSION_TASK_COMPLETED = "session.task_completed"
    SESSION_TASK_STARTED = "session.task_started"

    TASK_ESTIMATE_EXCEEDED = "task.estimate_exceeded"

    PLAN_CREATED = "plan.created"
    PLAN_COMPLETED = "plan.completed"

    GUARDIAN_NUDGE = "guardian.nudge"
    GUARDIAN_ESCALATION = "guardian.escalation"
    GUARDIAN_BURNOUT_WARNING = "guardian.burnout_warning"

    CHRONOS_CONFLICT = "chronos.conflict"
    CHRONOS_RESCHEDULE = "chronos.reschedule"
    CHRONOS_ESTIMATE_LEARNING = "chronos.estimate_learning"

    CALENDAR_EVENT_CREATED = "calendar.event_created"
    CALENDAR_EVENT_CHANGED = "calendar.event_changed"
    CALENDAR_EVENT_DELETED = "calendar.event_deleted"


# ---------------------------------------------------------------------------
# event model
# ---------------------------------------------------------------------------


class Event(BaseModel):
    """A single event published to the bus.

    Parameters
    ----------
    id : str
        Auto-generated 8-char hex identifier.
    topic : str
        Dot-delimited topic string (e.g. "plan.created").
    source : str
        Name of the component that emitted the event.
    data : dict
        Arbitrary payload data.
    timestamp : datetime
        UTC timestamp of when the event was created.
    session_id : str or None
        Optional session context.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    topic: str
    source: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: Optional[str] = None


# handler type alias
EventHandler = Callable[[Event], Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# event bus
# ---------------------------------------------------------------------------

_HISTORY_MAX = 1000


class EventBus:
    """Async pub/sub event bus with wildcard topic matching.

    Handlers are matched against topic patterns using ``fnmatch`` so that
    ``"plan.*"`` will match both ``"plan.created"`` and ``"plan.completed"``.

    The bus can run in two modes:

    1. **Background dispatch** — call ``start()`` to launch an ``asyncio.Task``
       that drains a queue and dispatches events to handlers.
    2. **Synchronous fallback** — if the bus is not started, ``publish()``
       dispatches directly (useful in tests without a running loop).
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[EventHandler]] = {}
        self._queue: asyncio.Queue[Event] = asyncio.Queue()
        self._dispatch_task: Optional[asyncio.Task] = None
        self._running: bool = False
        self._history: deque[Event] = deque(maxlen=_HISTORY_MAX)

    # -- subscription --------------------------------------------------------

    def subscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        """Register a handler for a topic pattern.

        Parameters
        ----------
        topic_pattern : str
            Glob-style pattern, e.g. ``"plan.*"`` or ``"guardian.nudge"``.
        handler : EventHandler
            Async callable that receives an ``Event``.
        """
        self._handlers.setdefault(topic_pattern, []).append(handler)

    def unsubscribe(self, topic_pattern: str, handler: EventHandler) -> None:
        """Remove a handler from a topic pattern."""
        handlers = self._handlers.get(topic_pattern, [])
        if handler in handlers:
            handlers.remove(handler)
            if not handlers:
                del self._handlers[topic_pattern]

    # -- publishing ----------------------------------------------------------

    async def publish(self, event: Event) -> None:
        """Publish an event to all matching handlers.

        If the background dispatch loop is running the event is queued;
        otherwise it is dispatched synchronously (direct await).
        """
        self._history.append(event)

        if self._running:
            await self._queue.put(event)
        else:
            await self._dispatch(event)

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> None:
        """Start the background dispatch loop.

        Must be called from within a running ``asyncio`` event loop.
        """
        if self._running:
            return
        self._running = True
        self._dispatch_task = asyncio.ensure_future(self._run_loop())

    async def stop(self) -> None:
        """Stop the background dispatch loop and drain remaining events."""
        if not self._running:
            return
        self._running = False

        # drain remaining events
        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                await self._dispatch(event)
            except asyncio.QueueEmpty:
                break

        if self._dispatch_task and not self._dispatch_task.done():
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
        self._dispatch_task = None

    @property
    def running(self) -> bool:
        """Whether the background dispatch loop is active."""
        return self._running

    # -- history -------------------------------------------------------------

    @property
    def history(self) -> list[Event]:
        """Return a copy of the event history ring buffer."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear the event history."""
        self._history.clear()

    # -- internals -----------------------------------------------------------

    async def _run_loop(self) -> None:
        """Background dispatch loop."""
        try:
            while self._running:
                try:
                    event = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                    await self._dispatch(event)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass

    async def _dispatch(self, event: Event) -> None:
        """Dispatch an event to all matching handlers with graceful degradation."""
        for pattern, handlers in self._handlers.items():
            if fnmatch(event.topic, pattern):
                for handler in handlers:
                    try:
                        await handler(event)
                    except Exception:
                        logger.exception(
                            "Event handler %s failed for topic %s",
                            getattr(handler, "__name__", repr(handler)),
                            event.topic,
                        )


# ---------------------------------------------------------------------------
# global singleton
# ---------------------------------------------------------------------------

_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global event bus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global event bus (primarily for testing)."""
    global _event_bus
    _event_bus = None
