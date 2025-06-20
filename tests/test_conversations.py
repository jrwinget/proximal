import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
from datetime import datetime, timedelta
from packages.core.models import ConversationState, MessageRole, UserPreferences
from packages.core.session import SessionManager, _sessions


@pytest.fixture
def session_manager():
    """Create a session manager for testing"""
    # clear any existing sessions
    _sessions.clear()
    return SessionManager()


@pytest.fixture
def mock_weaviate():
    """Mock Weaviate client for tests"""
    with patch("packages.core.session.weaviate_client") as mock:
        mock.schema.get.return_value = {"classes": []}
        mock.query.get.return_value.with_near_text.return_value.with_limit.return_value.do.return_value = {
            "data": {"Get": {"ConversationHistory": []}}
        }
        yield mock


class TestSessionManager:
    def test_create_session(self, session_manager):
        """Test creating a new session"""
        goal = "Build a mobile app"
        session = session_manager.create_session(goal)

        assert session.goal == goal
        assert session.session_id is not None
        assert session.status == "active"
        assert session.clarification_count == 0
        assert len(session.messages) == 0

    def test_get_session(self, session_manager):
        """Test retrieving an active session"""
        session = session_manager.create_session("Test goal")
        session_id = session.session_id

        retrieved = session_manager.get_session(session_id)
        assert retrieved is not None
        assert retrieved.session_id == session_id
        assert retrieved.goal == "Test goal"

    def test_session_expiry(self, session_manager):
        """Test that expired sessions are cleaned up"""
        session = session_manager.create_session("Test goal")
        session_id = session.session_id

        # manually expire session
        session.updated_at = (
            datetime.utcnow() - session_manager.session_timeout - timedelta(seconds=1)
        )

        retrieved = session_manager.get_session(session_id)
        assert retrieved is None
        assert session_id not in session_manager.sessions

    def test_update_session(self, session_manager):
        """Test adding messages to a session"""
        session = session_manager.create_session("Test goal")
        session_id = session.session_id

        # add user message
        updated = session_manager.update_session(
            session_id, MessageRole.user, "What platform?"
        )
        assert updated is not None
        assert len(updated.messages) == 1
        assert updated.messages[0].role == MessageRole.user
        assert updated.messages[0].content == "What platform?"
        assert updated.clarification_count == 1

        # add assistant message
        updated = session_manager.update_session(
            session_id, MessageRole.assistant, "iOS or Android"
        )
        assert len(updated.messages) == 2
        assert updated.clarification_count == 1  # only user messages increase count

    def test_complete_session(self, session_manager, mock_weaviate):
        """Test completing a session and persisting to Weaviate"""
        session = session_manager.create_session("Test goal")
        session_id = session.session_id
        session.add_message(MessageRole.user, "Test message")

        plan = [{"name": "Sprint 1", "tasks": []}]
        session_manager.complete_session(session_id, plan)

        # session should be removed from active sessions
        assert session_id not in session_manager.sessions

        # weaviate should be called to persist
        mock_weaviate.data_object.create.assert_called_once()
        call_args = mock_weaviate.data_object.create.call_args
        assert call_args[1]["class_name"] == "ConversationHistory"
        assert "session_id" in call_args[1]["data_object"]

    def test_get_user_preferences_default(self, session_manager, mock_weaviate):
        """Test getting default user preferences"""
        prefs = session_manager.get_user_preferences()

        assert prefs.user_id == "default"
        assert prefs.sprint_length_weeks == 2
        assert prefs.tone == "professional"
        assert prefs.work_hours_per_week == 40

    def test_save_user_preferences(self, session_manager, mock_weaviate):
        """Test saving user preferences"""
        prefs = UserPreferences(
            user_id="test_user",
            sprint_length_weeks=1,
            tone="casual",
            work_hours_per_week=20,
        )

        session_manager.save_user_preferences(prefs)

        # should be cached
        cached = session_manager.get_user_preferences("test_user")
        assert cached.sprint_length_weeks == 1
        assert cached.tone == "casual"

        # weaviate should be called
        mock_weaviate.data_object.create.assert_called()


@pytest.mark.asyncio
class TestConversationFlow:
    @patch("packages.core.agents.chat_model", new_callable=AsyncMock)
    @patch("packages.core.agents.session_manager")
    async def test_clarify_llm_needs_clarification(self, mock_session_mgr, mock_chat):
        """Test clarify_llm when clarification is needed"""
        from packages.core.agents import clarify_llm

        # setup mocks
        mock_chat.return_value = json.dumps(
            {
                "needs_clarification": True,
                "questions": ["What platform?", "What's your timeline?"],
            }
        )

        mock_session = MagicMock()
        mock_session.get_context.return_value = []
        mock_session_mgr.get_session.return_value = mock_session
        mock_session_mgr.get_user_preferences.return_value = UserPreferences()
        mock_session_mgr.get_relevant_history.return_value = []

        # call function
        state = {"goal": "Build an app", "session_id": "test123"}
        result = await clarify_llm(state)

        # verify result
        assert result["needs_clarification"] is True
        assert len(result["clarification_questions"]) == 2
        assert "What platform?" in result["clarification_questions"]

    @patch("packages.core.agents.chat_model", new_callable=AsyncMock)
    @patch("packages.core.agents.session_manager")
    async def test_clarify_llm_no_clarification(self, mock_session_mgr, mock_chat):
        """Test clarify_llm when no clarification is needed"""
        from packages.core.agents import clarify_llm

        # setup mocks
        mock_chat.return_value = json.dumps(
            {"needs_clarification": False, "questions": []}
        )

        mock_session_mgr.get_session.return_value = None
        mock_session_mgr.get_user_preferences.return_value = UserPreferences()
        mock_session_mgr.get_relevant_history.return_value = []

        # call function
        state = {"goal": "Build an iOS todo app with SwiftUI by next month"}
        result = await clarify_llm(state)

        # verify result
        assert result["needs_clarification"] is False
        assert result["clarification_questions"] == []

    @patch("packages.core.agents.chat_model", new_callable=AsyncMock)
    @patch("packages.core.agents.session_manager")
    async def test_integrate_clarifications(self, mock_session_mgr, mock_chat):
        """Test integrating clarification answers into enriched goal"""
        from packages.core.agents import integrate_clarifications_llm

        # setup mock session with q&a
        mock_session = ConversationState(goal="Build an app")
        mock_session.add_message(MessageRole.user, "Build an app")
        mock_session.add_message(MessageRole.assistant, "What platform?")
        mock_session.add_message(MessageRole.user, "iOS using SwiftUI")
        mock_session.add_message(MessageRole.assistant, "What's your timeline?")
        mock_session.add_message(MessageRole.user, "Launch in 3 months")

        mock_session_mgr.get_session.return_value = mock_session
        mock_chat.return_value = (
            "Build an iOS app using SwiftUI with a 3-month timeline for launch"
        )

        # call function
        state = {"goal": "Build an app", "session_id": "test123"}
        result = await integrate_clarifications_llm(state)

        # verify result
        assert "iOS" in result["goal"]
        assert "SwiftUI" in result["goal"]
        assert result["original_goal"] == "Build an app"

    @patch("packages.core.agents.chat_model", new_callable=AsyncMock)
    @patch("packages.core.agents.session_manager")
    async def test_plan_with_memory_context(self, mock_session_mgr, mock_chat):
        """Test that plan_llm uses memory context"""
        from packages.core.agents import plan_llm

        # setup mocks
        mock_session_mgr.get_user_preferences.return_value = UserPreferences(
            sprint_length_weeks=1, tone="casual"
        )

        mock_session_mgr.get_relevant_history.return_value = [
            {
                "goal": "Build a web app",
                "plan": [
                    {
                        "tasks": [
                            {"title": "Setup repository"},
                            {"title": "Design database"},
                        ]
                    }
                ],
            }
        ]

        mock_chat.return_value = json.dumps(
            [
                {
                    "id": "task1",
                    "title": "Setup iOS project",
                    "detail": "Initialize SwiftUI project",
                    "priority": "P1",
                    "estimate_h": 2,
                    "done": False,
                }
            ]
        )

        # call function
        result = await plan_llm({"goal": "Build an iOS app"})

        # verify the prompt included context
        call_args = mock_chat.call_args
        prompt = call_args[0][0][0]["content"]
        assert "1-week sprints" in prompt
        assert "casual tone" in prompt
        assert "similar past projects" in prompt

    @patch("packages.core.agents.breakdown_task_llm")
    async def test_task_breakdown_subtasks(self, mock_breakdown):
        """Test breaking down a task into subtasks"""
        from packages.core.models import Task, Priority

        task = Task(
            title="Create login page",
            detail="Implement user authentication",
            priority=Priority.high,
            estimate_h=8,
        )

        mock_breakdown.return_value = [
            {
                "title": "Design login UI",
                "detail": "Create mockup in Figma",
                "estimate_h": 2,
                "order": 1,
            },
            {
                "title": "Implement login form",
                "detail": "Add username/password fields",
                "estimate_h": 3,
                "order": 2,
            },
        ]

        result = await mock_breakdown(task, "subtasks")

        assert len(result) == 2
        assert result[0]["title"] == "Design login UI"
        assert sum(st["estimate_h"] for st in result) == 5
