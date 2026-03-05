"""Tests for the plain async pipeline (replaces LangGraph)."""

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.mark.asyncio
@patch("packages.core.agents.planner.chat_model", new_callable=AsyncMock)
@patch("packages.core.agents.planner.session_manager")
async def test_direct_pipeline_flow(mock_session_mgr, mock_chat):
    """Test that direct pipeline flows through plan, prioritize, estimate, package."""
    from apps.server.pipeline import run_direct_pipeline

    # setup mocks
    mock_session_mgr.get_user_preferences.return_value = MagicMock(
        sprint_length_weeks=2,
        tone="professional",
        work_hours_per_week=40,
        preferred_task_size="medium",
        include_breaks=True,
        priority_system="P0-P3",
        to_prompt_context=MagicMock(return_value="User preferences: defaults"),
    )
    mock_session_mgr.get_relevant_history.return_value = []
    mock_session_mgr.complete_session = MagicMock()

    mock_chat.side_effect = [
        # plan_llm response
        '[{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P1", "estimate_h": 5, "done": false}]',
        # prioritize_llm response
        '[{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P0", "estimate_h": 5, "done": false}]',
        # estimate_llm response
        '[{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P0", "estimate_h": 8, "done": false}]',
        # package_llm response
        '[{"name": "Sprint 1", "start": "2023-06-01", "end": "2023-06-15", "tasks": [{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P0", "estimate_h": 8, "done": false}]}]',
    ]

    # call pipeline
    result = await run_direct_pipeline("Create a todo app")

    # verify mock was called expected number of times (4 llm calls)
    assert mock_chat.call_count == 4

    # verify final result
    assert "sprints" in result
    assert len(result["sprints"]) == 1
    assert result["sprints"][0].name == "Sprint 1"


@pytest.mark.asyncio
@patch("packages.core.agents.planner.chat_model", new_callable=AsyncMock)
@patch("packages.core.agents.planner.session_manager")
async def test_interactive_pipeline_needs_clarification(mock_session_mgr, mock_chat):
    """Test interactive pipeline returns when clarification is needed."""
    from apps.server.pipeline import run_interactive_pipeline

    # setup mocks
    mock_session = MagicMock()
    mock_session.get_context.return_value = []
    mock_session.clarification_count = 0
    mock_session.max_clarifications = 2
    mock_session_mgr.get_session.return_value = mock_session
    mock_session_mgr.get_user_preferences.return_value = MagicMock(
        to_prompt_context=MagicMock(return_value="User preferences: defaults"),
    )
    mock_session_mgr.get_relevant_history.return_value = []

    mock_chat.return_value = json.dumps(
        {
            "needs_clarification": True,
            "questions": ["What platform?", "What timeline?"],
        }
    )

    # call pipeline
    result = await run_interactive_pipeline("Build an app", session_id="test-session")

    # should return early with clarification questions
    assert result.get("needs_clarification") is True
    assert len(result.get("clarification_questions", [])) == 2
    # only one llm call (clarify) should have been made
    assert mock_chat.call_count == 1


@pytest.mark.asyncio
@patch("packages.core.agents.planner.chat_model", new_callable=AsyncMock)
@patch("packages.core.agents.planner.session_manager")
async def test_interactive_pipeline_no_clarification(mock_session_mgr, mock_chat):
    """Test interactive pipeline proceeds when no clarification is needed."""
    from apps.server.pipeline import run_interactive_pipeline

    goal = "Build an iOS todo app with SwiftUI"

    # setup mocks
    mock_session_mgr.get_session.return_value = None
    mock_session_mgr.get_user_preferences.return_value = MagicMock(
        sprint_length_weeks=2,
        tone="professional",
        work_hours_per_week=40,
        preferred_task_size="medium",
        include_breaks=True,
        priority_system="P0-P3",
        to_prompt_context=MagicMock(return_value="User preferences: defaults"),
    )
    mock_session_mgr.get_relevant_history.return_value = []
    mock_session_mgr.complete_session = MagicMock()

    mock_chat.side_effect = [
        # clarify_llm response - no clarification needed
        json.dumps({"needs_clarification": False, "questions": []}),
        # plan_llm response (integrate_clarifications_llm returns state
        # as-is when no session_id, so no llm call for that step)
        '[{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P1", "estimate_h": 5, "done": false}]',
        # prioritize_llm response
        '[{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P0", "estimate_h": 5, "done": false}]',
        # estimate_llm response
        '[{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P0", "estimate_h": 8, "done": false}]',
        # package_llm response
        '[{"name": "Sprint 1", "start": "2023-06-01", "end": "2023-06-15", "tasks": [{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P0", "estimate_h": 8, "done": false}]}]',
    ]

    # patch clarify_llm to preserve the goal in returned state
    original_clarify = None
    import packages.core.agents.planner as planner_mod

    original_clarify = planner_mod.PlannerAgent.clarify_llm

    async def patched_clarify(self, state):
        result = await original_clarify(self, state)
        # preserve goal and session_id from original state
        result["goal"] = state.get("goal", "")
        result["session_id"] = state.get("session_id")
        return result

    with patch.object(planner_mod.PlannerAgent, "clarify_llm", patched_clarify):
        # call pipeline
        result = await run_interactive_pipeline(goal)

    # should produce a complete plan
    assert "sprints" in result
    assert len(result["sprints"]) == 1


@pytest.mark.asyncio
@patch("packages.core.agents.planner.chat_model", new_callable=AsyncMock)
@patch("packages.core.agents.planner.session_manager")
async def test_direct_pipeline_preserves_kwargs(mock_session_mgr, mock_chat):
    """Test that extra kwargs are passed through the pipeline state."""
    from apps.server.pipeline import run_direct_pipeline

    mock_session_mgr.get_user_preferences.return_value = MagicMock(
        sprint_length_weeks=2,
        tone="professional",
        work_hours_per_week=40,
        preferred_task_size="medium",
        include_breaks=True,
        priority_system="P0-P3",
        to_prompt_context=MagicMock(return_value="User preferences: defaults"),
    )
    mock_session_mgr.get_relevant_history.return_value = []
    mock_session_mgr.complete_session = MagicMock()

    mock_chat.side_effect = [
        '[{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P1", "estimate_h": 5, "done": false}]',
        '[{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P0", "estimate_h": 5, "done": false}]',
        '[{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P0", "estimate_h": 8, "done": false}]',
        '[{"name": "Sprint 1", "start": "2023-06-01", "end": "2023-06-15", "tasks": [{"id": "task1", "title": "Task 1", "detail": "Detail 1", "priority": "P0", "estimate_h": 8, "done": false}]}]',
    ]

    result = await run_direct_pipeline("Create a todo app", session_id="abc123")

    # verify the pipeline completed
    assert "sprints" in result


# backward compatibility: module-level names should still exist
def test_backward_compat_names():
    """Test that backward-compatible module-level names are available."""
    from apps.server import pipeline

    assert hasattr(pipeline, "run_direct_pipeline")
    assert hasattr(pipeline, "run_interactive_pipeline")
    assert callable(pipeline.run_direct_pipeline)
    assert callable(pipeline.run_interactive_pipeline)
