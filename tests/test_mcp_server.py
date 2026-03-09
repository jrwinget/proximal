"""Tests for MCP server exposing proximal planning capabilities."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from apps.mcp_server import (
    handle_break_down_task,
    handle_draft_message,
    handle_get_motivation,
    handle_plan_goal,
)


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_plan_goal_returns_structured_plan(mock_get_chat):
    """plan_goal should return tasks, schedule, and breaks."""
    mock_chat = AsyncMock(
        return_value=json.dumps(
            [
                {
                    "id": "t1",
                    "title": "Set up project",
                    "detail": "Initialize repo and tooling",
                    "priority": "P1",
                    "estimate_h": 2,
                    "done": False,
                }
            ]
        )
    )
    mock_get_chat.return_value = mock_chat

    result = await handle_plan_goal("Build a website", energy="medium")
    data = json.loads(result)

    assert "tasks" in data
    assert isinstance(data["tasks"], list)
    assert len(data["tasks"]) > 0
    assert "schedule" in data
    assert "breaks" in data


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_plan_goal_with_high_energy(mock_get_chat):
    """plan_goal should include energy level in prompt."""
    mock_chat = AsyncMock(
        return_value=json.dumps(
            [
                {
                    "id": "t1",
                    "title": "Design system",
                    "detail": "Create architecture",
                    "priority": "P0",
                    "estimate_h": 4,
                    "done": False,
                }
            ]
        )
    )
    mock_get_chat.return_value = mock_chat

    result = await handle_plan_goal("Redesign the API", energy="high")
    data = json.loads(result)

    assert "tasks" in data
    # verify the chat function was called with energy context
    call_args = mock_chat.call_args[0][0]
    assert any("high" in msg.get("content", "").lower() for msg in call_args)


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_plan_goal_handles_llm_error(mock_get_chat):
    """plan_goal should return an error message when the LLM fails."""
    mock_chat = AsyncMock(side_effect=Exception("LLM unavailable"))
    mock_get_chat.return_value = mock_chat

    result = await handle_plan_goal("Build something")
    data = json.loads(result)

    assert "error" in data


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_break_down_task_subtasks(mock_get_chat):
    """break_down_task should return subtasks by default."""
    mock_chat = AsyncMock(
        return_value=json.dumps(
            [
                {
                    "title": "Research",
                    "detail": "Research options",
                    "estimate_h": 1,
                    "order": 1,
                },
                {
                    "title": "Implement",
                    "detail": "Write code",
                    "estimate_h": 2,
                    "order": 2,
                },
            ]
        )
    )
    mock_get_chat.return_value = mock_chat

    result = await handle_break_down_task(
        "Implement auth", method="subtasks", hours=4.0
    )
    data = json.loads(result)

    assert "items" in data
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0
    assert data["method"] == "subtasks"


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_break_down_task_pomodoros(mock_get_chat):
    """break_down_task with pomodoros method should return sessions."""
    mock_chat = AsyncMock(
        return_value=json.dumps(
            [
                {"session_number": 1, "focus": "Read docs", "deliverable": "Notes"},
                {"session_number": 2, "focus": "Write code", "deliverable": "Draft"},
            ]
        )
    )
    mock_get_chat.return_value = mock_chat

    result = await handle_break_down_task(
        "Build login page", method="pomodoros", hours=2.0
    )
    data = json.loads(result)

    assert data["method"] == "pomodoros"
    assert "items" in data


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_break_down_task_handles_error(mock_get_chat):
    """break_down_task should return error on failure."""
    mock_chat = AsyncMock(side_effect=RuntimeError("timeout"))
    mock_get_chat.return_value = mock_chat

    result = await handle_break_down_task("Some task")
    data = json.loads(result)

    assert "error" in data


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_draft_message_returns_subject_and_body(mock_get_chat):
    """draft_message should return subject and body."""
    mock_chat = AsyncMock(
        return_value=json.dumps(
            {
                "subject": "Project Update: API Migration",
                "message": "The API migration is progressing well and on schedule.",
            }
        )
    )
    mock_get_chat.return_value = mock_chat

    result = await handle_draft_message(
        context="API migration project, 60% complete",
        message_type="status_update",
        tone="professional",
    )
    data = json.loads(result)

    assert "subject" in data
    assert "body" in data
    assert isinstance(data["subject"], str)
    assert isinstance(data["body"], str)


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_draft_message_different_types(mock_get_chat):
    """draft_message should handle various message types."""
    mock_chat = AsyncMock(
        return_value=json.dumps(
            {
                "subject": "Help Needed: Database Issue",
                "message": "I need help debugging a database connection issue.",
            }
        )
    )
    mock_get_chat.return_value = mock_chat

    result = await handle_draft_message(
        context="Database connection failing intermittently",
        message_type="help_request",
        tone="casual",
    )
    data = json.loads(result)

    assert "subject" in data
    assert "body" in data


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_draft_message_handles_error(mock_get_chat):
    """draft_message should return error on failure."""
    mock_chat = AsyncMock(side_effect=Exception("Model error"))
    mock_get_chat.return_value = mock_chat

    result = await handle_draft_message(context="Something")
    data = json.loads(result)

    assert "error" in data


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_get_motivation_returns_message(mock_get_chat):
    """get_motivation should return an encouraging message."""
    mock_chat = AsyncMock(
        return_value="You're making great progress! Every step forward counts."
    )
    mock_get_chat.return_value = mock_chat

    result = await handle_get_motivation(
        context="Working on a difficult refactor", energy="low"
    )
    data = json.loads(result)

    assert "message" in data
    assert isinstance(data["message"], str)
    assert len(data["message"]) > 0


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_get_motivation_with_different_energy_levels(mock_get_chat):
    """get_motivation should adapt to energy level."""
    mock_chat = AsyncMock(return_value="Keep pushing! You're on fire today!")
    mock_get_chat.return_value = mock_chat

    result = await handle_get_motivation(context="Coding a new feature", energy="high")
    data = json.loads(result)

    assert "message" in data
    # verify energy was passed to prompt
    call_args = mock_chat.call_args[0][0]
    assert any("high" in msg.get("content", "").lower() for msg in call_args)


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_get_motivation_handles_error(mock_get_chat):
    """get_motivation should return error on failure."""
    mock_chat = AsyncMock(side_effect=Exception("Unavailable"))
    mock_get_chat.return_value = mock_chat

    result = await handle_get_motivation(context="Anything")
    data = json.loads(result)

    assert "error" in data


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_plan_goal_invalid_json_from_llm(mock_get_chat):
    """plan_goal should handle non-JSON LLM responses gracefully."""
    mock_chat = AsyncMock(return_value="This is not valid JSON at all")
    mock_get_chat.return_value = mock_chat

    result = await handle_plan_goal("Build something")
    data = json.loads(result)

    assert "error" in data


@pytest.mark.asyncio
@patch("apps.mcp_server._get_chat_fn")
async def test_draft_message_invalid_json_from_llm(mock_get_chat):
    """draft_message should handle non-JSON LLM responses gracefully."""
    mock_chat = AsyncMock(return_value="Here is a nice status update for you!")
    mock_get_chat.return_value = mock_chat

    result = await handle_draft_message(context="Project update")
    data = json.loads(result)

    # should still produce a result using the raw text as body
    assert "subject" in data or "error" in data
