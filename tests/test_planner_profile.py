import json
from unittest.mock import AsyncMock, MagicMock, patch

from packages.core.agents.planner import PlannerAgent
from packages.core.collaboration.context import SharedContext
from packages.core.models import UserProfile


def _mock_tasks_response(n=6):
    """Return a list of n task dicts as JSON string."""
    tasks = []
    priorities = ["P0", "P1", "P2", "P3"]
    for i in range(n):
        tasks.append(
            {
                "id": str(i),
                "title": f"Task {i}",
                "detail": f"Detail for task {i}",
                "priority": priorities[i % 4],
                "estimate_h": 2,
            }
        )
    return json.dumps(tasks)


def _build_mock_litellm(n=6):
    """Build a litellm-shaped mock response."""
    message = MagicMock()
    message.content = _mock_tasks_response(n)
    message.tool_calls = None
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


async def test_high_decision_fatigue_caps_tasks(mock_litellm):
    """High decision fatigue caps the task list to overwhelm_threshold."""
    mock_litellm.return_value = _build_mock_litellm(6)

    profile = UserProfile(decision_fatigue="high", overwhelm_threshold=3)
    ctx = SharedContext(goal="Build an app", user_profile=profile)

    planner = PlannerAgent()
    with patch("packages.core.agents.planner.memory.store", new_callable=AsyncMock):
        result = await planner.run(ctx)

    assert len(result) == 3


async def test_high_fatigue_sorts_by_priority(mock_litellm):
    """Capped tasks are sorted with P0 first."""
    mock_litellm.return_value = _build_mock_litellm(6)

    profile = UserProfile(decision_fatigue="high", overwhelm_threshold=3)
    ctx = SharedContext(goal="Build an app", user_profile=profile)

    planner = PlannerAgent()
    with patch("packages.core.agents.planner.memory.store", new_callable=AsyncMock):
        result = await planner.run(ctx)

    # first task should be P0 (highest priority)
    assert result[0]["priority"] == "P0"
    # tasks should be in priority order
    prio_values = [{"P0": 0, "P1": 1, "P2": 2, "P3": 3}[t["priority"]] for t in result]
    assert prio_values == sorted(prio_values)


async def test_high_fatigue_marks_recommended_next(mock_litellm):
    """First task gets recommended_next=True when fatigue is high."""
    mock_litellm.return_value = _build_mock_litellm(6)

    profile = UserProfile(decision_fatigue="high", overwhelm_threshold=3)
    ctx = SharedContext(goal="Build an app", user_profile=profile)

    planner = PlannerAgent()
    with patch("packages.core.agents.planner.memory.store", new_callable=AsyncMock):
        result = await planner.run(ctx)

    assert result[0].get("recommended_next") is True
    # other tasks should not have recommended_next
    for task in result[1:]:
        assert "recommended_next" not in task


async def test_low_decision_fatigue_no_cap(mock_litellm):
    """Low decision fatigue returns all tasks without capping."""
    mock_litellm.return_value = _build_mock_litellm(6)

    profile = UserProfile(decision_fatigue="low", overwhelm_threshold=3)
    ctx = SharedContext(goal="Build an app", user_profile=profile)

    planner = PlannerAgent()
    with patch("packages.core.agents.planner.memory.store", new_callable=AsyncMock):
        result = await planner.run(ctx)

    assert len(result) == 6


async def test_moderate_fatigue_no_cap(mock_litellm):
    """Moderate decision fatigue returns all tasks (prompt context added but no cap)."""
    mock_litellm.return_value = _build_mock_litellm(6)

    profile = UserProfile(decision_fatigue="moderate", overwhelm_threshold=3)
    ctx = SharedContext(goal="Build an app", user_profile=profile)

    planner = PlannerAgent()
    with patch("packages.core.agents.planner.memory.store", new_callable=AsyncMock):
        result = await planner.run(ctx)

    assert len(result) == 6


async def test_decision_fatigue_in_prompt(mock_litellm):
    """LLM prompt includes decision fatigue context when high."""
    mock_litellm.return_value = _build_mock_litellm(6)

    profile = UserProfile(decision_fatigue="high", overwhelm_threshold=3)
    ctx = SharedContext(goal="Build an app", user_profile=profile)

    planner = PlannerAgent()
    with patch("packages.core.agents.planner.memory.store", new_callable=AsyncMock):
        await planner.run(ctx)

    # extract the prompt sent to litellm
    call_args = mock_litellm.call_args
    messages = call_args[1].get("messages") or call_args[0][0]
    prompt_content = messages[0]["content"]

    assert "high decision fatigue" in prompt_content


async def test_default_profile_backward_compat(mock_litellm):
    """Default profile (moderate fatigue) does not alter task count."""
    mock_litellm.return_value = _build_mock_litellm(6)

    # default SharedContext uses default UserProfile (moderate fatigue)
    ctx = SharedContext(goal="Build an app")

    planner = PlannerAgent()
    with patch("packages.core.agents.planner.memory.store", new_callable=AsyncMock):
        result = await planner.run(ctx)

    # all 6 tasks should be returned without modification
    assert len(result) == 6
    # no recommended_next flag on any task
    for task in result:
        assert "recommended_next" not in task
