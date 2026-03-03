"""Tests for interactive CLI commands and task breakdown."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest  # noqa: E402
from unittest.mock import patch, MagicMock, AsyncMock  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from apps.cli import app  # noqa: E402


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def interactive_conversation_flow():
    """Mock data for an interactive conversation flow"""
    return {
        "start_response": {
            "session_id": "test-session-123",
            "type": "questions",
            "questions": [
                "What platform do you want to target?",
                "What's your timeline?",
            ],
        },
        "continue_response": {
            "session_id": "test-session-123",
            "type": "plan",
            "plan": [
                {
                    "name": "Sprint 1",
                    "start": "2024-01-01",
                    "end": "2024-01-14",
                    "tasks": [
                        {
                            "id": "task1",
                            "title": "Setup iOS project",
                            "detail": "Initialize SwiftUI project",
                            "priority": "P1",
                            "estimate_h": 2,
                            "done": False,
                        }
                    ],
                }
            ],
        },
    }


class TestInteractivePlanning:
    @patch("apps.cli.httpx.post")
    @patch("apps.cli.Prompt.ask")
    def test_interactive_planning_flow_server(
        self, mock_prompt, mock_post, runner, interactive_conversation_flow
    ):
        """Test the full interactive planning flow via server"""
        # setup mocks
        mock_responses = [
            MagicMock(json=lambda: interactive_conversation_flow["start_response"]),
            MagicMock(json=lambda: interactive_conversation_flow["continue_response"]),
        ]
        for resp in mock_responses:
            resp.raise_for_status = MagicMock()

        mock_post.side_effect = mock_responses

        # mock user answers to questions
        mock_prompt.side_effect = ["iOS with SwiftUI", "3 months"]

        # run command with --server flag
        result = runner.invoke(
            app, ["plan", "Build a mobile app", "--interactive", "--server", "--no-pretty"]
        )

        # verify success
        assert result.exit_code == 0
        assert "Interactive Planning: Build a mobile app" in result.stdout
        assert "PlannerAgent Needs Some Clarification" in result.stdout

        # verify api calls
        assert mock_post.call_count == 2

        # first call to start conversation
        first_call = mock_post.call_args_list[0]
        assert "/conversation/start" in first_call[0][0]
        assert first_call[1]["json"]["message"] == "Build a mobile app"

        # second call to continue with answers
        second_call = mock_post.call_args_list[1]
        assert "/conversation/continue" in second_call[0][0]
        answers = second_call[1]["json"]["answers"]
        assert "What platform do you want to target?" in answers
        assert answers["What platform do you want to target?"] == "iOS with SwiftUI"

    @patch("apps.cli.httpx.post")
    def test_interactive_no_clarification_server(self, mock_post, runner):
        """Test interactive mode when no clarification is needed via server"""
        # setup mock - goes directly to plan
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "session_id": "test-session-456",
            "type": "plan",
            "plan": [
                {
                    "name": "Sprint 1",
                    "start": "2024-01-01",
                    "end": "2024-01-14",
                    "tasks": [],
                }
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # run command with --server flag
        result = runner.invoke(
            app,
            [
                "plan",
                "Build an iOS todo app with SwiftUI",
                "--interactive",
                "--server",
                "--no-pretty",
            ],
        )

        # verify success without questions
        assert result.exit_code == 0
        assert "Interactive Planning:" in result.stdout
        assert "clarification" not in result.stdout.lower()

        # only one api call
        assert mock_post.call_count == 1

    @patch("apps.cli._get_interactive_pipeline")
    def test_interactive_direct_mode_no_clarification(self, mock_get_pipeline, runner):
        """Test interactive plan in direct mode with no clarification."""
        # return dicts instead of pydantic models to avoid date serialization issues
        mock_pipeline = AsyncMock()
        mock_pipeline.return_value = {
            "needs_clarification": False,
            "sprints": [
                {
                    "name": "Sprint 1",
                    "start": "2024-01-01",
                    "end": "2024-01-14",
                    "tasks": [
                        {
                            "id": "task1",
                            "title": "Setup project",
                            "detail": "Initialize repo",
                            "priority": "P1",
                            "estimate_h": 2,
                            "done": False,
                        }
                    ],
                }
            ],
        }
        mock_get_pipeline.return_value = mock_pipeline

        result = runner.invoke(
            app,
            [
                "plan",
                "Build an iOS todo app",
                "--interactive",
                "--no-pretty",
            ],
        )

        assert result.exit_code == 0
        assert "Interactive Planning:" in result.stdout


class TestTaskBreakdown:
    @patch("apps.cli.httpx.post")
    def test_breakdown_subtasks(self, mock_post, runner):
        """Test breaking down a task into subtasks"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "task_id": "generated-id",
            "task_title": "Create login page",
            "breakdown_type": "subtasks",
            "breakdown": [
                {
                    "order": 1,
                    "title": "Design login UI",
                    "detail": "Create mockup in Figma",
                    "estimate_h": 2,
                },
                {
                    "order": 2,
                    "title": "Implement form",
                    "detail": "Add input fields",
                    "estimate_h": 3,
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # run command
        result = runner.invoke(
            app,
            [
                "breakdown",
                "Create login page",
                "--detail",
                "User authentication",
                "--hours",
                "5",
            ],
        )

        # verify output
        assert result.exit_code == 0
        assert "Breaking down task: Create login page" in result.stdout
        assert "Design login UI" in result.stdout
        assert "Implement form" in result.stdout
        assert "Total estimated hours: 5" in result.stdout

    @patch("apps.cli.httpx.post")
    def test_breakdown_pomodoros(self, mock_post, runner):
        """Test breaking down a task into pomodoro sessions"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "breakdown_type": "pomodoros",
            "breakdown": [
                {
                    "session_number": 1,
                    "focus": "Setup environment",
                    "deliverable": "Dev environment ready",
                },
                {
                    "session_number": 2,
                    "focus": "Write initial code",
                    "deliverable": "Basic structure complete",
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        # run command
        result = runner.invoke(
            app, ["breakdown", "Setup project", "--type", "pomodoros", "--hours", "2"]
        )

        # verify output
        assert result.exit_code == 0
        assert "Pomodoro Sessions" in result.stdout
        assert "Setup environment" in result.stdout


class TestPreferences:
    @patch("apps.cli.httpx.get")
    def test_show_preferences(self, mock_get, runner):
        """Test showing current preferences"""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "user_id": "default",
            "sprint_length_weeks": 2,
            "work_hours_per_week": 40,
            "tone": "professional",
            "preferred_task_size": "medium",
            "include_breaks": True,
            "timezone": "UTC",
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        # run command
        result = runner.invoke(app, ["preferences"])

        # verify output
        assert result.exit_code == 0
        assert "Current Planning Preferences" in result.stdout
        assert "Sprint Length" in result.stdout
        assert "2 weeks" in result.stdout
        assert "Work Hours/Week" in result.stdout
        assert "40" in result.stdout

    @patch("apps.cli.httpx.put")
    @patch("apps.cli.httpx.get")
    def test_update_preferences(self, mock_get, mock_put, runner):
        """Test updating preferences"""
        # mock PUT response
        mock_put_response = MagicMock()
        mock_put_response.raise_for_status = MagicMock()
        mock_put.return_value = mock_put_response

        # mock GET response
        mock_get_response = MagicMock()
        mock_get_response.json.return_value = {
            "sprint_length_weeks": 1,
            "work_hours_per_week": 20,
            "tone": "casual",
            "preferred_task_size": "small",
            "include_breaks": True,
            "timezone": "UTC",
        }
        mock_get_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_get_response

        # run command
        result = runner.invoke(
            app,
            [
                "preferences",
                "--sprint-weeks",
                "1",
                "--work-hours",
                "20",
                "--tone",
                "casual",
            ],
        )

        # verify success
        assert result.exit_code == 0
        assert "Preferences Updated Successfully" in result.stdout

        # verify PUT was called with correct data
        mock_put.assert_called_once()
        put_data = mock_put.call_args[1]["json"]
        assert put_data["sprint_length_weeks"] == 1
        assert put_data["work_hours_per_week"] == 20
        assert put_data["tone"] == "casual"


class TestCLIErrorHandling:
    @patch("apps.cli.httpx.post")
    def test_keyboard_interrupt_handling(self, mock_post, runner):
        """Test that Ctrl+C is handled gracefully"""
        mock_post.side_effect = KeyboardInterrupt()

        result = runner.invoke(app, ["plan", "Test", "--interactive", "--server"])

        assert result.exit_code == 0
        assert "cancelled by user" in result.stdout.lower()

    @patch("apps.cli.httpx.post")
    def test_connection_error_interactive_server(self, mock_post, runner):
        """Test connection error handling in interactive server mode"""
        import httpx

        mock_post.side_effect = httpx.RequestError("Connection failed")

        result = runner.invoke(app, ["plan", "Test", "--interactive", "--server"])

        assert result.exit_code == 1
        assert "Could not connect to API server" in result.stdout
