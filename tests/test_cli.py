"""Tests for CLI commands, including direct (no-server) mode."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from unittest.mock import AsyncMock, MagicMock, patch  # noqa: E402

import pytest  # noqa: E402
from typer.testing import CliRunner  # noqa: E402

from apps.cli import app  # noqa: E402


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def sample_plan_data():
    """Sample plan data for testing."""
    return [
        {
            "name": "Sprint 1",
            "start": "2023-06-01",
            "end": "2023-06-15",
            "tasks": [
                {
                    "id": "task1",
                    "title": "Create login page",
                    "detail": "Implement user authentication",
                    "priority": "P1",
                    "estimate_h": 8,
                    "done": False,
                },
                {
                    "id": "task2",
                    "title": "Design database schema",
                    "detail": "Define data models and relationships",
                    "priority": "P0",
                    "estimate_h": 5,
                    "done": False,
                },
            ],
        }
    ]


def test_version(runner):
    """Test the version command."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Proximal CLI" in result.stdout


@patch("apps.cli.run_direct_pipeline", new_callable=AsyncMock)
def test_plan_command_direct_mode(mock_pipeline, runner):
    """Test plan command calls pipeline directly (no server)."""
    # return dicts instead of pydantic models to avoid date serialization issues
    mock_pipeline.return_value = {
        "sprints": [
            {
                "name": "Sprint 1",
                "start": "2023-06-01",
                "end": "2023-06-15",
                "tasks": [
                    {
                        "id": "task1",
                        "title": "Create login page",
                        "detail": "Implement user authentication",
                        "priority": "P1",
                        "estimate_h": 8,
                        "done": False,
                    }
                ],
            }
        ]
    }

    result = runner.invoke(app, ["plan", "Create a todo app", "--no-pretty"])

    assert result.exit_code == 0
    assert "Planning: Create a todo app" in result.stdout
    mock_pipeline.assert_called_once()


@patch("apps.cli.httpx.post")
def test_plan_command_server_mode(mock_post, runner, sample_plan_data):
    """Test plan command with --server flag uses HTTP."""
    mock_response = MagicMock()
    mock_response.json.return_value = sample_plan_data
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    result = runner.invoke(
        app, ["plan", "Create a todo app", "--server", "--no-pretty"]
    )

    assert result.exit_code == 0
    assert "Planning: Create a todo app" in result.stdout

    # verify mock was called with correct arguments
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:7315/plan"
    assert kwargs["json"] == {"message": "Create a todo app"}


@patch("apps.cli.run_direct_pipeline", new_callable=AsyncMock)
def test_plan_command_with_output_file(mock_pipeline, runner, tmp_path):
    """Test plan command with output to a file (direct mode)."""
    # return dicts instead of pydantic models to avoid date serialization issues
    mock_pipeline.return_value = {
        "sprints": [
            {
                "name": "Sprint 1",
                "start": "2023-06-01",
                "end": "2023-06-15",
                "tasks": [
                    {
                        "id": "task1",
                        "title": "Create login page",
                        "detail": "Implement user auth",
                        "priority": "P1",
                        "estimate_h": 8,
                        "done": False,
                    }
                ],
            }
        ]
    }

    output_file = tmp_path / "plan.json"
    result = runner.invoke(
        app, ["plan", "Create a todo app", "-o", str(output_file), "--no-pretty"]
    )

    assert result.exit_code == 0
    assert str(output_file) in result.stdout
    assert "Plan saved to" in result.stdout
    assert output_file.exists()


@patch("apps.cli.httpx.post")
def test_plan_command_server_api_error(mock_post, runner):
    """Test plan command with --server when API returns error."""
    from httpx import HTTPStatusError, Request, Response

    mock_response = Response(status_code=500, content=b"Internal Server Error")
    mock_response._request = Request(method="POST", url="http://localhost:7315/plan")
    mock_post.side_effect = HTTPStatusError(
        "Error", request=mock_response.request, response=mock_response
    )

    result = runner.invoke(app, ["plan", "Create a todo app", "--server"])

    assert result.exit_code == 1
    assert "Error: HTTP 500" in result.stdout


@patch("apps.cli.httpx.post")
def test_plan_command_server_connection_error(mock_post, runner):
    """Test plan command with --server when server is unreachable."""
    from httpx import RequestError

    mock_post.side_effect = RequestError("Connection error")

    result = runner.invoke(app, ["plan", "Create a todo app", "--server"])

    assert result.exit_code == 1
    assert "Could not connect to API server" in result.stdout


@patch("apps.cli.run_direct_pipeline", new_callable=AsyncMock)
def test_plan_command_direct_error(mock_pipeline, runner):
    """Test plan command handles pipeline errors gracefully."""
    mock_pipeline.side_effect = Exception("LLM call failed")

    result = runner.invoke(app, ["plan", "Create a todo app"])

    assert result.exit_code == 1
    assert "Error" in result.stdout


@patch("apps.cli.run_interactive_pipeline", new_callable=AsyncMock)
def test_plan_interactive_direct_mode_needs_clarification(mock_pipeline, runner):
    """Test interactive plan in direct mode with clarification questions."""
    # first call returns questions
    mock_pipeline.return_value = {
        "needs_clarification": True,
        "clarification_questions": ["What platform?"],
        "session_id": "test-session",
        "goal": "Build an app",
    }

    # this will fail because Prompt.ask is not mocked, but the pipeline call should happen
    # we test the non-interactive path separately
    result = runner.invoke(
        app, ["plan", "Build an app", "--interactive", "--no-pretty"], input="iOS\n"
    )

    # the interactive flow should have started
    assert "Interactive Planning" in result.stdout
