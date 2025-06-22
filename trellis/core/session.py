from abc import ABC, abstractmethod
from typing import Dict, Optional, List
from datetime import datetime, timedelta, timezone
import json
import os

from .models import (
    ConversationState,
    ConversationMessage,
    MessageRole,
    UserPreferences,
)
from .memory import client as weaviate_client

# in-memory session store
_sessions: Dict[str, ConversationState] = {}

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
    """Redis session store (requires Redis and pickle)"""

    def __init__(self, url: str):
        import redis
        import pickle

        self.client = redis.from_url(url)
        self.pickle = pickle

    def get(self, session_id: str) -> Optional[ConversationState]:
        data = self.client.get(session_id)
        return self.pickle.loads(data) if data else None

    def save(self, session: ConversationState) -> None:
        data = self.pickle.dumps(session)
        self.client.set(session.session_id, data)

    def delete(self, session_id: str) -> None:
        self.client.delete(session_id)

    def all(self) -> Dict[str, ConversationState]:
        result = {}
        for key in self.client.keys():
            raw = self.client.get(key)
            result[key.decode()] = self.pickle.loads(raw)
        return result


class SessionManager:
    """Manages conversation sessions with pluggable store"""

    def __init__(self, store: SessionStore = None):
        # default to in-memory store
        self.store = store or InMemoryStore()
        self.sessions = _sessions
        self.session_timeout = timedelta(hours=1)
        self._ensure_weaviate_schemas()

    def _ensure_weaviate_schemas(self):
        """Ensure Weaviate has required schemas"""
        if os.getenv("SKIP_WEAVIATE_CONNECTION"):
            return

        schema = weaviate_client.schema.get()
        classes = [c["class"] for c in schema.get("classes", [])]

        if "ConversationHistory" not in classes:
            weaviate_client.schema.create_class(
                {
                    "class": "ConversationHistory",
                    "properties": [
                        {"name": "session_id", "dataType": ["text"]},
                        {"name": "goal", "dataType": ["text"]},
                        {"name": "messages", "dataType": ["text"]},
                        {"name": "final_plan", "dataType": ["text"]},
                        {"name": "created_at", "dataType": ["date"]},
                    ],
                }
            )

        if "UserPreferences" not in classes:
            weaviate_client.schema.create_class(
                {
                    "class": "UserPreferences",
                    "properties": [
                        {"name": "user_id", "dataType": ["text"]},
                        {"name": "preferences", "dataType": ["text"]},
                        {"name": "updated_at", "dataType": ["date"]},
                    ],
                }
            )

    def create_session(self, initial_goal: str) -> ConversationState:
        """Create a new conversation session"""
        session = ConversationState(goal=initial_goal)
        self.store.save(session)
        return session

    def get_session(self, session_id: str) -> Optional[ConversationState]:
        """Retrieve an active session"""
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
        """Add a message to the session"""
        session = self.get_session(session_id)
        if not session:
            return None
        session.add_message(role, content)
        if role == MessageRole.user:
            session.clarification_count += 1
        self.store.save(session)
        return session

    def complete_session(
        self, session_id: str, final_plan: Optional[List] = None
    ) -> None:
        """Mark session as complete and persist to Weaviate"""
        session = self.get_session(session_id)
        if not session:
            return

        session.status = "completed"

        if os.getenv("SKIP_WEAVIATE_CONNECTION"):
            # clean up in-memory only
            self.store.delete(session_id)
            return

        # prepare historical record
        messages_data = []
        for msg in session.messages:
            d = msg.model_dump()
            d["timestamp"] = msg.timestamp.isoformat()
            messages_data.append(d)

        history_data = {
            "session_id": session.session_id,
            "goal": session.goal,
            "messages": json.dumps(messages_data),
            "final_plan": json.dumps(final_plan) if final_plan is not None else None,
            "created_at": session.created_at.isoformat(),
        }

        weaviate_client.data_object.create(
            data_object=history_data,
            class_name="ConversationHistory",
        )

        # clean up session store
        self.store.delete(session_id)

    def get_relevant_history(self, query: str, limit: int = 3) -> List[Dict]:
        """Retrieve relevant past conversations using vector search"""
        if os.getenv("SKIP_WEAVIATE_CONNECTION"):
            return []
        try:
            result = (
                weaviate_client.query.get(
                    "ConversationHistory", ["goal", "messages", "final_plan"]
                )
                .with_near_text({"concepts": [query]})
                .with_limit(limit)
                .do()
            )
            entries = (
                result.get("data", {}).get("Get", {}).get("ConversationHistory", [])
            )
            out = []
            for h in entries:
                out.append(
                    {
                        "goal": h["goal"],
                        "messages": json.loads(h["messages"])
                        if h.get("messages")
                        else [],
                        "plan": json.loads(h["final_plan"])
                        if h.get("final_plan")
                        else None,
                    }
                )
            return out
        except Exception:
            return []

    def get_user_preferences(self, user_id: str = "default") -> UserPreferences:
        """Get user preferences from cache or Weaviate"""
        global _preferences_cache

        if _preferences_cache and _preferences_cache.user_id == user_id:
            return _preferences_cache

        if os.getenv("SKIP_WEAVIATE_CONNECTION"):
            _preferences_cache = UserPreferences(user_id=user_id)
            return _preferences_cache

        try:
            result = (
                weaviate_client.query.get("UserPreferences", ["user_id", "preferences"])
                .with_where(
                    {
                        "path": ["user_id"],
                        "operator": "Equal",
                        "valueText": user_id,
                    }
                )
                .do()
            )
            prefs_list = (
                result.get("data", {}).get("Get", {}).get("UserPreferences", [])
            )
            if prefs_list:
                data = json.loads(prefs_list[0]["preferences"])
                _preferences_cache = UserPreferences(**data)
                return _preferences_cache
        except Exception:
            pass

        _preferences_cache = UserPreferences(user_id=user_id)
        return _preferences_cache

    def save_user_preferences(self, preferences: UserPreferences):
        """Save user preferences to Weaviate and cache in memory"""
        global _preferences_cache
        _preferences_cache = preferences

        if os.getenv("SKIP_WEAVIATE_CONNECTION"):
            return

        pref_data = preferences.model_dump()
        pref_data["updated_at"] = preferences.updated_at.isoformat()

        try:
            weaviate_client.data_object.create(
                data_object=pref_data,
                class_name="UserPreferences",
            )
        except Exception:
            pass


session_manager = SessionManager()
