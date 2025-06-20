import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# mock session manager before importing app
with patch("packages.core.session.weaviate_client"):
    from apps.server.main import app
    from packages.core.models import ConversationState, Sprint, Task, Priority
    from packages.core.session import _sessions


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture
def mock_session_manager():
    """Mock the session manager"""
    with patch("apps.server.main.session_manager") as mock:
        yield mock


@pytest.fixture
def sample_conversation_state():
    """Create a sample conversation state"""
    state = ConversationState(goal="Build a mobile app")
    state.session_id = "test-session-123"
    return state


@pytest.fixture
def sample_plan():
    """Create a sample plan"""
    return [
        Sprint(
            name="Sprint 1",
            start="2024-01-01",
            end="2024-01-14",
            tasks=[
                Task(
                    id="t1",
                    title="Setup project",
                    detail="Initialize repository",
                    priority=Priority.high,
                    estimate_h=2,
                )
            ],
        )
    ]


class TestConversationAPI:
    @patch("apps.server.main.INTERACTIVE_PIPELINE.ainvoke", new_callable=AsyncMock)
    def test_start_conversation_with_questions(
        self, mock_pipeline, client, mock_session_manager, sample_conversation_state
    ):
        """Test starting a conversation that needs clarification"""
        # setup mocks
        mock_session_manager.create_session.return_value = sample_conversation_state
        mock_session_manager.get_user_preferences.return_value = MagicMock()
        mock_session_manager.save_user_preferences = MagicMock()

        mock_pipeline.return_value = {
            "needs_clarification": True,
            "clarification_questions": ["What platform?", "What's your timeline?"],
        }

        # make request
        response = client.post(
            "/conversation/start", json={"message": "Build a mobile app"}
        )

        # verify response
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert data["type"] == "questions"
        assert len(data["questions"]) == 2
        assert "What platform?" in data["questions"]

    @patch("apps.server.main.INTERACTIVE_PIPELINE.ainvoke", new_callable=AsyncMock)
    def test_start_conversation_direct_to_plan(
        self,
        mock_pipeline,
        client,
        mock_session_manager,
        sample_conversation_state,
        sample_plan,
    ):
        """Test starting a conversation that goes directly to planning"""
        # setup mocks
        mock_session_manager.create_session.return_value = sample_conversation_state
        mock_session_manager.get_user_preferences.return_value = MagicMock()

        mock_pipeline.return_value = {
            "needs_clarification": False,
            "sprints": sample_plan,
        }

        # make request
        response = client.post(
            "/conversation/start",
            json={"message": "Build an iOS todo app with SwiftUI by next month"},
        )

        # verify response
        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert data["type"] == "plan"
        assert len(data["plan"]) == 1
        assert data["plan"][0]["name"] == "Sprint 1"

    def test_start_conversation_with_preferences(
        self, client, mock_session_manager, sample_conversation_state
    ):
        """Test starting a conversation with preference updates"""
        # setup mocks
        mock_session_manager.create_session.return_value = sample_conversation_state
        mock_prefs = MagicMock()
        mock_session_manager.get_user_preferences.return_value = mock_prefs

        # make request with preferences
        response = client.post(
            "/conversation/start",
            json={
                "message": "Build an app",
                "preferences": {"sprint_length_weeks": 1, "tone": "casual"},
            },
        )

        # verify preferences were updated
        assert response.status_code == 200
        mock_session_manager.save_user_preferences.assert_called_once()

    @patch("apps.server.main.integrate_clarifications_llm", new_callable=AsyncMock)
    @patch("apps.server.main.plan_llm", new_callable=AsyncMock)
    @patch("apps.server.main.prioritize_llm", new_callable=AsyncMock)
    @patch("apps.server.main.estimate_llm", new_callable=AsyncMock)
    @patch("apps.server.main.package_llm", new_callable=AsyncMock)
    def test_continue_conversation(
        self,
        mock_package,
        mock_estimate,
        mock_prioritize,
        mock_plan,
        mock_integrate,
        client,
        mock_session_manager,
        sample_conversation_state,
        sample_plan,
    ):
        """Test continuing a conversation with answers"""
        # setup mocks
        sample_conversation_state.clarification_count = 1
        mock_session_manager.get_session.return_value = sample_conversation_state

        mock_integrate.return_value = {
            "goal": "Enriched goal",
            "session_id": "test-session-123",
        }
        mock_plan.return_value = {"tasks": []}
        mock_prioritize.return_value = {"tasks": []}
        mock_estimate.return_value = {"tasks": []}
        mock_package.return_value = {"sprints": sample_plan}

        # make request
        response = client.post(
            "/conversation/continue",
            json={
                "session_id": "test-session-123",
                "answers": {"What platform?": "iOS", "Timeline?": "3 months"},
            },
        )

        # verify response
        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "plan"
        assert len(data["plan"]) == 1

        # verify conversation was updated
        sample_conversation_state.add_message.assert_called()

    def test_continue_nonexistent_session(self, client, mock_session_manager):
        """Test continuing a session that doesn't exist"""
        mock_session_manager.get_session.return_value = None

        response = client.post(
            "/conversation/continue",
            json={"session_id": "nonexistent", "answers": "Some answer"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_conversation_status(
        self, client, mock_session_manager, sample_conversation_state
    ):
        """Test getting conversation status"""
        sample_conversation_state.add_message("user", "Test message")
        mock_session_manager.get_session.return_value = sample_conversation_state

        response = client.get("/conversation/test-session-123")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "test-session-123"
        assert data["status"] == "active"
        assert len(data["messages"]) == 1


class TestTaskBreakdownAPI:
    @patch("apps.server.main.breakdown_task_llm", new_callable=AsyncMock)
    def test_breakdown_task_subtasks(self, mock_breakdown, client):
        """Test breaking down a task into subtasks"""
        mock_breakdown.return_value = [
            {
                "title": "Design UI",
                "detail": "Create mockup",
                "estimate_h": 2,
                "order": 1,
            }
        ]

        task = Task(
            id="t1",
            title="Create login page",
            detail="Build the login",
            priority=Priority.high,
            estimate_h=8,
        )

        response = client.post(
            "/task/breakdown",
            json={"task": task.model_dump(), "breakdown_type": "subtasks"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "t1"
        assert data["breakdown_type"] == "subtasks"
        assert len(data["breakdown"]) == 1
        assert data["breakdown"][0]["title"] == "Design UI"

    @patch("apps.server.main.breakdown_task_llm", new_callable=AsyncMock)
    def test_breakdown_task_pomodoros(self, mock_breakdown, client):
        """Test breaking down a task into pomodoros"""
        mock_breakdown.return_value = [
            {
                "session_number": 1,
                "focus": "Setup environment",
                "deliverable": "Dev environment ready",
            }
        ]

        task = Task(
            id="t2",
            title="Setup project",
            detail="Initialize repo",
            priority=Priority.medium,
            estimate_h=2,
        )

        response = client.post(
            "/task/breakdown",
            json={"task": task.model_dump(), "breakdown_type": "pomodoros"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["breakdown_type"] == "pomodoros"
        assert data["breakdown"][0]["focus"] == "Setup environment"


class TestPreferencesAPI:
    def test_get_preferences(self, client, mock_session_manager):
        """Test getting user preferences"""
        mock_prefs = MagicMock()
        mock_prefs.model_dump.return_value = {
            "user_id": "default",
            "sprint_length_weeks": 2,
            "tone": "professional",
            "work_hours_per_week": 40,
            "preferred_task_size": "medium",
            "include_breaks": True,
            "timezone": "UTC",
        }
        mock_session_manager.get_user_preferences.return_value = mock_prefs

        response = client.get("/preferences")

        assert response.status_code == 200
        data = response.json()
        assert data["sprint_length_weeks"] == 2
        assert data["tone"] == "professional"

    def test_update_preferences(self, client, mock_session_manager):
        """Test updating user preferences"""
        mock_prefs = MagicMock()
        mock_session_manager.get_user_preferences.return_value = mock_prefs

        response = client.put(
            "/preferences",
            json={
                "sprint_length_weeks": 1,
                "tone": "casual",
                "work_hours_per_week": 20,
            },
        )

        assert response.status_code == 200
        mock_session_manager.save_user_preferences.assert_called_once()

        # verify attributes were set
        assert mock_prefs.sprint_length_weeks == 1
        assert mock_prefs.tone == "casual"
        assert mock_prefs.work_hours_per_week == 20
