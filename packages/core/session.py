import asyncio
import json
import os
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from . import memory
from .events import Event, Topics, get_event_bus
from .models import (
    ConversationState,
    MessageRole,
    UserPreferences,
)


def _try_publish(bus, event: Event) -> None:
    """Fire-and-forget event publish; never raises."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        loop.create_task(bus.publish(event))
    else:
        # no running loop; skip publish silently
        pass


# in-memory session store
_sessions: Dict[str, ConversationState] = {}

# locks for preventing race conditions on session access
_session_locks: Dict[str, threading.Lock] = {}

# single-user preferences cache
_preferences_cache: Optional[UserPreferences] = None


class SessionStore(ABC):
    """abstract interface for session persistence backends"""

    @abstractmethod
    def get(self, session_id: str) -> Optional[ConversationState]: ...

    @abstractmethod
    def save(self, session: ConversationState) -> None: ...

    @abstractmethod
    def delete(self, session_id: str) -> None: ...

    @abstractmethod
    def all(self) -> Dict[str, ConversationState]: ...


class InMemoryStore(SessionStore):
    """In-memory session store using module-level dict"""

    def get(self, session_id: str) -> Optional[ConversationState]:
        return _sessions.get(session_id)

    def save(self, session: ConversationState) -> None:
        _sessions[session.session_id] = session

    def delete(self, session_id: str) -> None:
        _sessions.pop(session_id, None)

    def all(self) -> Dict[str, ConversationState]:
        return dict(_sessions)


class RedisStore(SessionStore):
    """Redis session store using JSON serialization (secure alternative to pickle)"""

    def __init__(self, url: str):
        import redis

        self.client = redis.from_url(url)

    def get(self, session_id: str) -> Optional[ConversationState]:
        """retrieve session from redis and deserialize from json"""
        import logging

        logger = logging.getLogger(__name__)

        data = self.client.get(session_id)
        if not data:
            return None

        try:
            # decode bytes to string, then parse json
            json_str = data.decode("utf-8")
            session_dict = json.loads(json_str)
            # use pydantic to reconstruct the model with validation
            return ConversationState.model_validate(session_dict)
        except (json.JSONDecodeError, ValueError) as e:
            # corrupted data - delete and return None
            logger.warning(f"Failed to deserialize session {session_id}: {e}")
            self.delete(session_id)
            return None

    def save(self, session: ConversationState) -> None:
        """serialize session to json and store in redis"""
        # convert pydantic model to dict, handling datetime serialization
        session_dict = session.model_dump(mode="json")
        # serialize to json string
        json_str = json.dumps(session_dict)
        # store in redis with optional expiry (24 hours)
        self.client.set(session.session_id, json_str, ex=86400)

    def delete(self, session_id: str) -> None:
        """remove session from redis"""
        self.client.delete(session_id)

    def all(self) -> Dict[str, ConversationState]:
        """retrieve all sessions - use scan_iter to avoid blocking redis"""
        result = {}
        # use scan_iter instead of keys() to avoid blocking
        for key in self.client.scan_iter(match="*"):
            raw = self.client.get(key)
            if raw:
                try:
                    json_str = raw.decode("utf-8")
                    session_dict = json.loads(json_str)
                    result[key.decode()] = ConversationState.model_validate(
                        session_dict
                    )
                except (json.JSONDecodeError, ValueError):
                    # skip corrupted entries
                    continue
        return result


def _run_async(coro):
    """Run an async coroutine from synchronous code."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # we're inside an async context; create a task but can't await here
        # use a new event loop in a thread
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    else:
        return asyncio.run(coro)


class SessionManager:
    """Manages conversation sessions with pluggable store"""

    def __init__(self, store: SessionStore = None):
        from .settings import get_settings

        settings = get_settings()

        # use redis if configured, otherwise fall back to in-memory with warning
        if store:
            self.store = store
        elif settings.redis_url:
            try:
                import logging

                logger = logging.getLogger(__name__)
                self.store = RedisStore(settings.redis_url)
                logger.info("Using Redis For Session Storage")
            except Exception as e:
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Failed To Connect To Redis ({settings.redis_url}): {e}. "
                    "Falling Back To In-Memory Sessions - Data Will Be Lost On Restart"
                )
                self.store = InMemoryStore()
        else:
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                "Using In-Memory Sessions - Data Will Be Lost On Restart. "
                "Set REDIS_URL For Production Deployments"
            )
            self.store = InMemoryStore()

        self.sessions = _sessions
        self.session_timeout = timedelta(hours=settings.session_timeout_hours)
        self.locks = _session_locks

    def _get_lock(self, session_id: str) -> threading.Lock:
        """Get or create a lock for a specific session"""
        if session_id not in self.locks:
            self.locks[session_id] = threading.Lock()
        return self.locks[session_id]

    def create_session(self, initial_goal: str) -> ConversationState:
        """Create a new conversation session with locking"""
        session = ConversationState(goal=initial_goal)
        lock = self._get_lock(session.session_id)
        with lock:
            self.store.save(session)

        # publish session.started event (fire-and-forget)
        try:
            bus = get_event_bus()
            event = Event(
                topic=Topics.SESSION_STARTED,
                source="session",
                data={"goal": initial_goal},
                session_id=session.session_id,
            )
            _try_publish(bus, event)
        except Exception:
            pass

        return session

    def get_session(self, session_id: str) -> Optional[ConversationState]:
        """Retrieve an active session with locking to prevent race conditions"""
        lock = self._get_lock(session_id)
        with lock:
            session = self.store.get(session_id)
            if session and self._is_session_valid(session):
                return session
            if session:
                # clean up expired session
                self.store.delete(session_id)
            return None

    def _is_session_valid(self, session: ConversationState) -> bool:
        """Check if session is still valid (not timed out)"""
        age = datetime.now(timezone.utc) - session.updated_at
        return age < self.session_timeout

    def update_session(
        self, session_id: str, role: MessageRole, content: str
    ) -> Optional[ConversationState]:
        """Add a message to the session with locking to prevent race conditions"""
        lock = self._get_lock(session_id)
        with lock:
            session = self.store.get(session_id)
            if not session or not self._is_session_valid(session):
                return None
            session.add_message(role, content)
            if role == MessageRole.user:
                session.clarification_count += 1
            self.store.save(session)
            return session

    def complete_session(
        self, session_id: str, final_plan: Optional[List] = None
    ) -> None:
        """Mark session as complete and persist to SQLite"""
        # publish session.ended event (fire-and-forget)
        try:
            bus = get_event_bus()
            event = Event(
                topic=Topics.SESSION_ENDED,
                source="session",
                session_id=session_id,
                data={"final_plan": bool(final_plan)},
            )
            _try_publish(bus, event)
        except Exception:
            pass

        lock = self._get_lock(session_id)
        with lock:
            session = self.store.get(session_id)
            if not session:
                return

            session.status = "completed"

            if os.getenv("SKIP_DB_CONNECTION") or os.getenv("SKIP_WEAVIATE_CONNECTION"):
                # clean up in-memory only
                self.store.delete(session_id)
                # clean up lock after session is deleted
                if session_id in self.locks:
                    del self.locks[session_id]
                return

            # prepare historical record
            messages_data = []
            for msg in session.messages:
                d = msg.model_dump()
                d["timestamp"] = msg.timestamp.isoformat()
                messages_data.append(d)

            history_data = {
                "goal": session.goal,
                "messages": messages_data,
                "final_plan": final_plan,
            }

            _run_async(memory.store_conversation(session.session_id, history_data))

            # clean up session store
            self.store.delete(session_id)

        # clean up lock after session is deleted
        if session_id in self.locks:
            del self.locks[session_id]

    def get_relevant_history(self, query: str, limit: int = 3) -> List[Dict]:
        """Retrieve relevant past conversations using full-text search"""
        import logging

        logger = logging.getLogger(__name__)

        if os.getenv("SKIP_DB_CONNECTION") or os.getenv("SKIP_WEAVIATE_CONNECTION"):
            return []
        try:
            return _run_async(memory.get_conversation_history(query, limit=limit))
        except Exception as e:
            logger.warning(f"Failed to retrieve history: {e}")
            return []

    def get_user_preferences(self, user_id: str = "default") -> UserPreferences:
        """Get user preferences from cache or SQLite"""
        import logging

        logger = logging.getLogger(__name__)
        global _preferences_cache

        if _preferences_cache and _preferences_cache.user_id == user_id:
            return _preferences_cache

        if os.getenv("SKIP_DB_CONNECTION") or os.getenv("SKIP_WEAVIATE_CONNECTION"):
            _preferences_cache = UserPreferences(user_id=user_id)
            return _preferences_cache

        try:
            prefs_data = _run_async(memory.get_preferences(user_id))
            if prefs_data:
                _preferences_cache = UserPreferences(**prefs_data)
                return _preferences_cache
        except Exception as e:
            logger.warning(f"Failed to load preferences: {e}")

        _preferences_cache = UserPreferences(user_id=user_id)
        return _preferences_cache

    def save_user_preferences(self, preferences: UserPreferences) -> None:
        """Save user preferences to SQLite and cache in memory"""
        import logging

        logger = logging.getLogger(__name__)
        global _preferences_cache
        _preferences_cache = preferences

        if os.getenv("SKIP_DB_CONNECTION") or os.getenv("SKIP_WEAVIATE_CONNECTION"):
            return

        try:
            pref_data = preferences.model_dump()
            # convert datetime fields to strings for json
            for key in ("created_at", "updated_at"):
                if key in pref_data and hasattr(pref_data[key], "isoformat"):
                    pref_data[key] = pref_data[key].isoformat()
            _run_async(memory.store_preferences(preferences.user_id, pref_data))
        except Exception as e:
            logger.warning(f"Failed to save preferences: {e}")


session_manager = SessionManager()
