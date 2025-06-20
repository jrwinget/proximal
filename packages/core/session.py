from typing import Dict, Optional, List
from datetime import datetime, timedelta, timezone
import json
from .models import ConversationState, ConversationMessage, MessageRole, UserPreferences
from .memory import client as weaviate_client
import os

# in-memory session store (consider replacing with redis)
_sessions: Dict[str, ConversationState] = {}
_preferences_cache: Optional[UserPreferences] = None


class SessionManager:
    """Manages conversation sessions with hybrid memory approach"""

    def __init__(self):
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
                        {"name": "messages", "dataType": ["text"]},  # JSON
                        {"name": "final_plan", "dataType": ["text"]},  # JSON
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
                        {"name": "preferences", "dataType": ["text"]},  # JSON
                        {"name": "updated_at", "dataType": ["date"]},
                    ],
                }
            )

    def create_session(self, initial_goal: str) -> ConversationState:
        """Create a new conversation session"""
        session = ConversationState(goal=initial_goal)
        self.sessions[session.session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[ConversationState]:
        """Retrieve an active session"""
        session = self.sessions.get(session_id)
        if session and self._is_session_valid(session):
            return session
        elif session:
            # clean up expired session
            del self.sessions[session_id]
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
        if session:
            session.add_message(role, content)
            if role == MessageRole.user:
                session.clarification_count += 1
            return session
        return None

    def complete_session(self, session_id: str, final_plan: Optional[List] = None):
        """Mark session as complete and persist to Weaviate"""
        session = self.get_session(session_id)
        if not session:
            return

        session.status = "completed"

        # skip weaviate in test mode
        if os.getenv("SKIP_WEAVIATE_CONNECTION"):
            return

        # persist to weaviate for long-term memory
        # convert messages to JSON-serializable format
        messages_data = []
        for msg in session.messages:
            msg_dict = msg.model_dump()
            msg_dict["timestamp"] = msg.timestamp.isoformat()
            messages_data.append(msg_dict)

        history_data = {
            "session_id": session.session_id,
            "goal": session.goal,
            "messages": json.dumps(messages_data),
            "final_plan": json.dumps(final_plan) if final_plan else None,
            "created_at": session.created_at.isoformat(),
        }

        weaviate_client.data_object.create(
            data_object=history_data, class_name="ConversationHistory"
        )

        # clean up in-memory session
        del self.sessions[session_id]

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

            histories = (
                result.get("data", {}).get("Get", {}).get("ConversationHistory", [])
            )
            return [
                {
                    "goal": h["goal"],
                    "messages": json.loads(h["messages"]) if h.get("messages") else [],
                    "plan": json.loads(h["final_plan"])
                    if h.get("final_plan")
                    else None,
                }
                for h in histories
            ]
        except Exception:
            return []

    def get_user_preferences(self, user_id: str = "default") -> UserPreferences:
        """Get user preferences from cache or Weaviate"""
        global _preferences_cache

        # return cached if available
        if _preferences_cache and _preferences_cache.user_id == user_id:
            return _preferences_cache

        # skip weaviate in test mode
        if os.getenv("SKIP_WEAVIATE_CONNECTION"):
            _preferences_cache = UserPreferences(user_id=user_id)
            return _preferences_cache

        # try to fetch from weaviate
        try:
            result = (
                weaviate_client.query.get("UserPreferences", ["user_id", "preferences"])
                .with_where(
                    {"path": ["user_id"], "operator": "Equal", "valueText": user_id}
                )
                .do()
            )

            prefs_data = (
                result.get("data", {}).get("Get", {}).get("UserPreferences", [])
            )
            if prefs_data:
                pref_json = json.loads(prefs_data[0]["preferences"])
                _preferences_cache = UserPreferences(**pref_json)
                return _preferences_cache
        except Exception:
            pass

        # defaults if not found
        _preferences_cache = UserPreferences(user_id=user_id)
        return _preferences_cache

    def save_user_preferences(self, preferences: UserPreferences):
        """
        Save user preferences to Weaviate and cache in memory.
        """
        global _preferences_cache
        # cache the latest preferences object (single-user model)
        _preferences_cache = preferences

        # skip remote persistence if flagged
        if os.getenv("SKIP_WEAVIATE_CONNECTION"):
            return

        pref_data = preferences.model_dump()
        pref_data["updated_at"] = preferences.updated_at.isoformat()

        # always attempt to persist (weaviate handles duplicates/errors)
        try:
            weaviate_client.data_object.create(
                data_object=pref_data,
                class_name="UserPreferences",
            )
        except Exception:
            pass


session_manager = SessionManager()
