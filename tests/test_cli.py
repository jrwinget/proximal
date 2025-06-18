import pytest
from unittest.mock import patch, MagicMock
import json
import sys
from pathlib import Path
from typer.testing import CliRunner

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from apps.cli import app


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
    assert "Trellis CLI" in result.stdout


@patch("apps.cli.httpx.post")
def test_plan_command_success(mock_post, runner, sample_plan_data):
    """Test the plan command with a successful API response."""
    # setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = sample_plan_data
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # run command
    result = runner.invoke(app, ["plan", "Create a todo app", "--no-pretty"])

    # verify result
    assert result.exit_code == 0
    assert "Planning: Create a todo app" in result.stdout

    # verify mock was called with correct arguments
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "http://localhost:7315/plan"
    assert kwargs["json"] == {"message": "Create a todo app"}


@patch("apps.cli.httpx.post")
def test_plan_command_with_output_file(mock_post, runner, sample_plan_data, tmp_path):
    """Test the plan command with output to a file."""
    # setup mock response
    mock_response = MagicMock()
    mock_response.json.return_value = sample_plan_data
    mock_response.raise_for_status.return_value = None
    mock_post.return_value = mock_response

    # create temp output file
    output_file = tmp_path / "plan.json"

    # run command with --no-pretty to avoid the table output
    result = runner.invoke(
        app, ["plan", "Create a todo app", "-o", str(output_file), "--no-pretty"]
    )

    # verify result
    assert result.exit_code == 0
    # Check that the output file path is mentioned somewhere in the output
    assert str(output_file) in result.stdout
    assert "Plan saved to" in result.stdout

    # verify file was created with correct content
    assert output_file.exists()
    with open(output_file) as f:
        saved_data = json.load(f)
    assert saved_data == sample_plan_data


@patch("apps.cli.httpx.post")
def test_plan_command_api_error(mock_post, runner):
    """Test the plan command with an API error."""
    # setup mock to raise an exception
    from httpx import HTTPStatusError, Response, Request

    mock_response = Response(status_code=500, content=b"Internal Server Error")
    mock_response._request = Request(method="POST", url="http://localhost:7315/plan")
    mock_post.side_effect = HTTPStatusError(
        "Error", request=mock_response.request, response=mock_response
    )

    # run command
    result = runner.invoke(app, ["plan", "Create a todo app"])

    # verify result
    assert result.exit_code == 1
    assert "Error: HTTP 500" in result.stdout


@patch("apps.cli.httpx.post")
def test_plan_command_connection_error(mock_post, runner):
    """Test the plan command with a connection error."""
    # setup mock to raise a connection exception
    from httpx import RequestError

    mock_post.side_effect = RequestError("Connection error")

    # run command
    result = runner.invoke(app, ["plan", "Create a todo app"])

    # verify result
    assert result.exit_code == 1
    assert "Could not connect to API server" in result.stdout
