import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json
from datetime import date, timedelta
from packages.core.agents import plan_llm, prioritize_llm, estimate_llm, package_llm
from packages.core.models import Task, Sprint, Priority


class DateEncoder(json.JSONEncoder):
    """Custom JSON encoder for date objects."""

    def default(self, obj):
        if isinstance(obj, date):
            return obj.isoformat()
        return super().default(obj)


@pytest.fixture
def sample_tasks():
    """Create sample tasks for testing."""
    return [
        Task(
            id="task1",
            title="Create login page",
            detail="Implement user authentication",
            priority=Priority.high,
            estimate_h=8,
        ),
        Task(
            id="task2",
            title="Design database schema",
            detail="Define data models and relationships",
            priority=Priority.critical,
            estimate_h=5,
        ),
    ]


@pytest.fixture
def sample_tasks_json(sample_tasks):
    """Create JSON representation of sample tasks."""
    return json.dumps([task.model_dump() for task in sample_tasks])


@pytest.fixture
def sample_sprints(sample_tasks):
    """Create sample sprints for testing."""
    today = date.today()
    return [
        Sprint(
            name="Sprint 1",
            start=today,
            end=today + timedelta(days=14),
            tasks=sample_tasks,
        )
    ]


@pytest.fixture
def sample_sprints_json(sample_sprints):
    """Create JSON representation of sample sprints."""
    return json.dumps(
        [sprint.model_dump(mode="json") for sprint in sample_sprints], cls=DateEncoder
    )


@pytest.mark.asyncio
@patch("packages.core.agents.chat_model", new_callable=AsyncMock)
@patch("packages.core.agents.mem", new_callable=MagicMock)
async def test_plan_llm(mock_mem, mock_chat, sample_tasks_json):
    """Test plan_llm function."""
    # setup mock
    mock_chat.return_value = sample_tasks_json
    mock_mem.batch.add_data_object = MagicMock()

    # call function
    result = await plan_llm({"goal": "Create a todo app"})

    # verify result
    assert "tasks" in result
    assert len(result["tasks"]) == 2
    assert all(isinstance(task, Task) for task in result["tasks"])

    # verify mock was called
    mock_chat.assert_called_once()
    mock_mem.batch.add_data_object.assert_called_once()


@pytest.mark.asyncio
@patch("packages.core.agents.chat_model", new_callable=AsyncMock)
async def test_prioritize_llm(mock_chat, sample_tasks, sample_tasks_json):
    """Test prioritize_llm function."""
    # setup mock
    mock_chat.return_value = sample_tasks_json

    # call function
    result = await prioritize_llm({"tasks": sample_tasks})

    # verify result
    assert "tasks" in result
    assert len(result["tasks"]) == 2
    assert all(isinstance(task, Task) for task in result["tasks"])

    # verify mock was called
    mock_chat.assert_called_once()


@pytest.mark.asyncio
@patch("packages.core.agents.chat_model", new_callable=AsyncMock)
async def test_estimate_llm(mock_chat, sample_tasks, sample_tasks_json):
    """Test estimate_llm function."""
    # setup mock
    mock_chat.return_value = sample_tasks_json

    # call function
    result = await estimate_llm({"tasks": sample_tasks})

    # verify result
    assert "tasks" in result
    assert len(result["tasks"]) == 2
    assert all(isinstance(task, Task) for task in result["tasks"])
    assert all(task.estimate_h > 0 for task in result["tasks"])

    # verify mock was called
    mock_chat.assert_called_once()


@pytest.mark.asyncio
@patch("packages.core.agents.chat_model", new_callable=AsyncMock)
@patch("packages.core.agents.mem", new_callable=MagicMock)
@patch(
    "packages.core.agents._json", return_value="{}"
)  # mock _json to avoid date serialization issues
async def test_package_llm(
    mock_json, mock_mem, mock_chat, sample_tasks, sample_sprints_json
):
    """Test package_llm function."""
    # setup mock
    mock_chat.return_value = sample_sprints_json
    mock_mem.batch.add_data_object = MagicMock()

    # call function
    result = await package_llm({"tasks": sample_tasks})

    # verify result
    assert "sprints" in result
    assert len(result["sprints"]) == 1
    assert all(isinstance(sprint, Sprint) for sprint in result["sprints"])

    # verify mock was called
    mock_chat.assert_called_once()
    mock_mem.batch.add_data_object.assert_called_once()
