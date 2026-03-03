import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# --- registry tests ---


def test_register_capability():
    """register_capability decorator should add capability to the registry."""
    from packages.core.capabilities.registry import (
        Capability,
        CAPABILITY_REGISTRY,
        register_capability,
    )

    @register_capability(
        name="test_cap",
        description="A test capability",
        category="test",
        requires_llm=False,
    )
    def my_func():
        return "hello"

    assert "test_cap" in CAPABILITY_REGISTRY
    cap = CAPABILITY_REGISTRY["test_cap"]
    assert isinstance(cap, Capability)
    assert cap.name == "test_cap"
    assert cap.description == "A test capability"
    assert cap.category == "test"
    assert cap.requires_llm is False
    assert cap.fn() == "hello"

    # cleanup
    del CAPABILITY_REGISTRY["test_cap"]


def test_register_capability_preserves_function():
    """register_capability should return the original function unchanged."""
    from packages.core.capabilities.registry import (
        CAPABILITY_REGISTRY,
        register_capability,
    )

    @register_capability(name="test_preserve", description="test")
    def original_fn(x: int) -> int:
        return x * 2

    assert original_fn(5) == 10

    # cleanup
    del CAPABILITY_REGISTRY["test_preserve"]


def test_capability_dataclass_defaults():
    """Capability dataclass should have sensible defaults."""
    from packages.core.capabilities.registry import Capability

    cap = Capability(name="x", description="y", fn=lambda: None)
    assert cap.requires_llm is False
    assert cap.category == "planning"


def test_capability_registry_init():
    """Capability __init__.py should expose the registry and decorator."""
    from packages.core.capabilities import (
        CAPABILITY_REGISTRY,
        register_capability,
    )

    assert isinstance(CAPABILITY_REGISTRY, dict)
    assert callable(register_capability)


# --- productivity capability tests ---


def test_create_schedule_capability():
    """create_schedule capability should produce hourly blocks with breaks."""
    from packages.core.capabilities.productivity import create_schedule

    tasks = [{"title": f"Task {i}"} for i in range(5)]
    schedule = create_schedule(tasks)

    assert isinstance(schedule, list)
    assert len(schedule) > len(tasks)  # breaks are added
    assert schedule[0]["start"] == "09:00"
    # break should appear after every 3 tasks
    break_items = [s for s in schedule if s.get("task", {}).get("title") == "Break"]
    assert len(break_items) >= 1


def test_create_focus_sessions_capability():
    """create_focus_sessions should return 25-minute sessions."""
    from packages.core.capabilities.productivity import create_focus_sessions

    tasks = [{"title": "A"}, {"title": "B"}]
    sessions = create_focus_sessions(tasks)
    assert len(sessions) == 2
    assert sessions[0]["duration_min"] == 25
    assert sessions[0]["task"] == "A"


# --- wellness capability tests ---


def test_add_wellness_nudges_capability():
    """add_wellness_nudges should insert breaks every 4 tasks."""
    from packages.core.capabilities.wellness import add_wellness_nudges

    tasks = [{"title": f"T{i}"} for i in range(5)]
    result = add_wellness_nudges(tasks)
    assert len(result) > len(tasks)
    nudges = [t for t in result if t.get("type") == "nudge"]
    assert len(nudges) >= 1


def test_motivate_capability():
    """motivate should return encouragement with the goal included."""
    from packages.core.capabilities.wellness import motivate

    msg = motivate("Build an app")
    assert "Build an app" in msg
    assert isinstance(msg, str)


# --- communication capability tests ---


@pytest.mark.asyncio
async def test_draft_message_capability():
    """draft_message capability should delegate to LiaisonAgent."""
    from packages.core.capabilities.communication import draft_message

    # mock the liaison agent's draft_message
    mock_result = {
        "subject": "Test",
        "message": "Hello world message body here",
        "tone": "professional",
        "estimated_tokens": 10,
        "metadata": {"generation_method": "llm"},
    }

    with patch(
        "packages.core.capabilities.communication.LiaisonAgent"
    ) as mock_liaison_cls:
        mock_instance = MagicMock()
        mock_instance.draft_message = AsyncMock(return_value=mock_result)
        mock_liaison_cls.return_value = mock_instance

        result = await draft_message("Test goal")
        assert result["subject"] == "Test"
        assert "Hello world" in result["message"]


# --- planning capability tests ---


@pytest.mark.asyncio
async def test_clarify_capability():
    """clarify capability should call planner's clarify_llm."""
    mock_result = {"needs_clarification": False, "clarification_questions": []}

    with patch(
        "packages.core.capabilities.planning.PlannerAgent"
    ) as mock_planner_cls:
        mock_instance = MagicMock()
        mock_instance.clarify_llm = AsyncMock(return_value=mock_result)
        mock_planner_cls.return_value = mock_instance

        from packages.core.capabilities.planning import clarify

        result = await clarify({"goal": "Build an app"})
        assert result["needs_clarification"] is False


@pytest.mark.asyncio
async def test_plan_capability():
    """plan capability should call planner's plan_llm."""
    mock_task = MagicMock()
    mock_result = {"tasks": [mock_task]}

    mock_instance = MagicMock()
    mock_instance.plan_llm = AsyncMock(return_value=mock_result)

    # reset the cached singleton and inject our mock
    import packages.core.capabilities.planning as planning_mod

    original_planner = planning_mod._planner
    planning_mod._planner = mock_instance
    try:
        from packages.core.capabilities.planning import plan

        result = await plan({"goal": "Build an app"})
        assert "tasks" in result
    finally:
        planning_mod._planner = original_planner


# --- backward compatibility tests ---


def test_agent_registry_still_works():
    """AGENT_REGISTRY should still contain all agents after capability migration."""
    from packages.core.agents import AGENT_REGISTRY

    expected_agents = ["planner", "chronos", "guardian", "mentor", "liaison", "scribe", "focusbuddy"]
    for name in expected_agents:
        assert name in AGENT_REGISTRY, f"Agent '{name}' missing from AGENT_REGISTRY"


def test_capability_registry_populated():
    """CAPABILITY_REGISTRY should contain migrated capabilities."""
    from packages.core.capabilities import CAPABILITY_REGISTRY

    expected = [
        "create_schedule",
        "create_focus_sessions",
        "add_wellness_nudges",
        "motivate",
        "draft_message",
        "clarify",
        "plan",
        "prioritize",
        "estimate",
        "package_tasks",
    ]
    for name in expected:
        assert name in CAPABILITY_REGISTRY, f"Capability '{name}' not registered"


def test_capability_requires_llm_flags():
    """LLM capabilities should have requires_llm=True."""
    from packages.core.capabilities import CAPABILITY_REGISTRY

    llm_caps = ["clarify", "plan", "prioritize", "estimate", "package_tasks", "draft_message"]
    for name in llm_caps:
        cap = CAPABILITY_REGISTRY[name]
        assert cap.requires_llm is True, f"Capability '{name}' should require LLM"

    deterministic_caps = ["create_schedule", "create_focus_sessions", "add_wellness_nudges", "motivate"]
    for name in deterministic_caps:
        cap = CAPABILITY_REGISTRY[name]
        assert cap.requires_llm is False, f"Capability '{name}' should not require LLM"


def test_capability_categories():
    """Capabilities should have appropriate categories."""
    from packages.core.capabilities import CAPABILITY_REGISTRY

    assert CAPABILITY_REGISTRY["create_schedule"].category == "productivity"
    assert CAPABILITY_REGISTRY["create_focus_sessions"].category == "productivity"
    assert CAPABILITY_REGISTRY["add_wellness_nudges"].category == "wellness"
    assert CAPABILITY_REGISTRY["motivate"].category == "wellness"
    assert CAPABILITY_REGISTRY["draft_message"].category == "communication"
    assert CAPABILITY_REGISTRY["clarify"].category == "planning"
    assert CAPABILITY_REGISTRY["plan"].category == "planning"
