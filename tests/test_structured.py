import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from pydantic import BaseModel

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# --- test models ---


class SimpleResult(BaseModel):
    answer: str
    confidence: float


class ClarificationResult(BaseModel):
    needs_clarification: bool
    questions: list[str]


class TaskItem(BaseModel):
    title: str
    priority: str
    estimate_h: int


class TaskListResult(BaseModel):
    tasks: list[TaskItem]


# --- helpers ---


def _make_tool_call_response(tool_name: str, arguments: dict) -> MagicMock:
    """Build a mock litellm response with a tool call."""
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = tool_name
    mock_tool_call.function.arguments = json.dumps(arguments)

    mock_choice = MagicMock()
    mock_choice.message.content = None
    mock_choice.message.tool_calls = [mock_tool_call]

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


# --- tests ---


@pytest.mark.asyncio
async def test_structured_output_simple_model():
    """structured_output should return a validated pydantic model."""
    response = _make_tool_call_response(
        "respond", {"answer": "42", "confidence": 0.95}
    )

    with patch("packages.core.structured.chat", new_callable=AsyncMock, return_value=response):
        from packages.core.structured import structured_output

        result = await structured_output(
            prompt="What is the answer?",
            response_model=SimpleResult,
        )
        assert isinstance(result, SimpleResult)
        assert result.answer == "42"
        assert result.confidence == 0.95


@pytest.mark.asyncio
async def test_structured_output_clarification_model():
    """structured_output should work with ClarificationResult."""
    response = _make_tool_call_response(
        "respond",
        {"needs_clarification": True, "questions": ["What platform?", "What timeline?"]},
    )

    with patch("packages.core.structured.chat", new_callable=AsyncMock, return_value=response):
        from packages.core.structured import structured_output

        result = await structured_output(
            prompt="Check if goal needs clarification",
            response_model=ClarificationResult,
        )
        assert result.needs_clarification is True
        assert len(result.questions) == 2


@pytest.mark.asyncio
async def test_structured_output_nested_model():
    """structured_output should work with nested pydantic models."""
    response = _make_tool_call_response(
        "respond",
        {
            "tasks": [
                {"title": "Setup DB", "priority": "P0", "estimate_h": 4},
                {"title": "Write API", "priority": "P1", "estimate_h": 8},
            ]
        },
    )

    with patch("packages.core.structured.chat", new_callable=AsyncMock, return_value=response):
        from packages.core.structured import structured_output

        result = await structured_output(
            prompt="Plan the tasks",
            response_model=TaskListResult,
        )
        assert isinstance(result, TaskListResult)
        assert len(result.tasks) == 2
        assert result.tasks[0].title == "Setup DB"


@pytest.mark.asyncio
async def test_structured_output_custom_tool_name():
    """structured_output should use custom tool_name."""
    response = _make_tool_call_response(
        "plan_tasks", {"answer": "yes", "confidence": 1.0}
    )

    with patch("packages.core.structured.chat", new_callable=AsyncMock, return_value=response) as mock_chat:
        from packages.core.structured import structured_output

        await structured_output(
            prompt="Test",
            response_model=SimpleResult,
            tool_name="plan_tasks",
            tool_description="Plan the tasks",
        )
        call_kwargs = mock_chat.call_args.kwargs
        tools = call_kwargs["tools"]
        assert tools[0]["function"]["name"] == "plan_tasks"
        assert tools[0]["function"]["description"] == "Plan the tasks"


@pytest.mark.asyncio
async def test_structured_output_with_system_prompt():
    """structured_output should include system prompt when provided."""
    response = _make_tool_call_response("respond", {"answer": "ok", "confidence": 1.0})

    with patch("packages.core.structured.chat", new_callable=AsyncMock, return_value=response) as mock_chat:
        from packages.core.structured import structured_output

        await structured_output(
            prompt="Test",
            response_model=SimpleResult,
            system_prompt="You are a planner.",
        )
        call_kwargs = mock_chat.call_args.kwargs
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "You are a planner."


@pytest.mark.asyncio
async def test_structured_output_no_system_prompt():
    """structured_output should omit system message when system_prompt is None."""
    response = _make_tool_call_response("respond", {"answer": "ok", "confidence": 1.0})

    with patch("packages.core.structured.chat", new_callable=AsyncMock, return_value=response) as mock_chat:
        from packages.core.structured import structured_output

        await structured_output(
            prompt="Test",
            response_model=SimpleResult,
        )
        call_kwargs = mock_chat.call_args.kwargs
        messages = call_kwargs["messages"]
        assert messages[0]["role"] == "user"


@pytest.mark.asyncio
async def test_structured_output_no_tool_calls_raises():
    """structured_output should raise ValueError when no tool calls in response."""
    mock_choice = MagicMock()
    mock_choice.message.content = "plain text"
    mock_choice.message.tool_calls = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("packages.core.structured.chat", new_callable=AsyncMock, return_value=mock_response):
        from packages.core.structured import structured_output

        with pytest.raises(ValueError, match="[Nn]o tool"):
            await structured_output(
                prompt="Test",
                response_model=SimpleResult,
            )


@pytest.mark.asyncio
async def test_structured_output_invalid_json_raises():
    """structured_output should raise ValueError for invalid JSON in tool call."""
    mock_tool_call = MagicMock()
    mock_tool_call.function.name = "respond"
    mock_tool_call.function.arguments = "not valid json{{"

    mock_choice = MagicMock()
    mock_choice.message.content = None
    mock_choice.message.tool_calls = [mock_tool_call]

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]

    with patch("packages.core.structured.chat", new_callable=AsyncMock, return_value=mock_response):
        from packages.core.structured import structured_output

        with pytest.raises(ValueError, match="[Pp]arse|[Jj]son|[Ii]nvalid"):
            await structured_output(
                prompt="Test",
                response_model=SimpleResult,
            )


@pytest.mark.asyncio
async def test_structured_output_validation_error_raises():
    """structured_output should raise ValueError when pydantic validation fails."""
    # missing required field 'confidence'
    response = _make_tool_call_response("respond", {"answer": "test"})

    with patch("packages.core.structured.chat", new_callable=AsyncMock, return_value=response):
        from packages.core.structured import structured_output

        with pytest.raises(ValueError, match="[Vv]alidat"):
            await structured_output(
                prompt="Test",
                response_model=SimpleResult,
            )


@pytest.mark.asyncio
async def test_structured_output_builds_tool_schema():
    """structured_output should generate correct JSON schema from pydantic model."""
    response = _make_tool_call_response("respond", {"answer": "ok", "confidence": 0.5})

    with patch("packages.core.structured.chat", new_callable=AsyncMock, return_value=response) as mock_chat:
        from packages.core.structured import structured_output

        await structured_output(
            prompt="Test",
            response_model=SimpleResult,
        )
        call_kwargs = mock_chat.call_args.kwargs
        tools = call_kwargs["tools"]
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        schema = tools[0]["function"]["parameters"]
        assert "answer" in schema["properties"]
        assert "confidence" in schema["properties"]
