import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.mark.asyncio
@patch("packages.core.agents.planner.chat_model", new_callable=AsyncMock)
@patch("packages.core.agents.planner.mem", new_callable=MagicMock)
@patch(
    "packages.core.agents.planner._json", return_value="{}"
)  # mock _json to avoid date serialization issues
async def test_pipeline_flow(mock_json, mock_mem, mock_chat):
    """Test that pipeline flows through all expected steps."""
    # import here to ensure patches are applied first
    from apps.server.pipeline import PIPELINE

    # setup mocks
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
    initial_state = {"goal": "Create a todo app"}
    result = await PIPELINE.ainvoke(initial_state)

    # verify mock was called expected number of times
    assert mock_chat.call_count == 4

    # verify final result
    assert "sprints" in result
    assert len(result["sprints"]) == 1
    assert result["sprints"][0].name == "Sprint 1"
