import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from packages.proximal.agents import AGENT_REGISTRY
from packages.proximal.agents.chronos import ChronosAgent
from packages.proximal.orchestrator import Orchestrator


def test_agent_registration():
    """ChronosAgent should be registered in the global registry."""
    assert AGENT_REGISTRY.get("chronos") is ChronosAgent


def test_chronos_schedule():
    agent = ChronosAgent()
    tasks = [{"title": f"Task {i}"} for i in range(5)]
    schedule = agent.create_schedule(tasks)
    # expect break after third task
    assert len(schedule) == 6
    assert schedule[0]["start"] == "09:00"
    assert schedule[0]["end"] == "10:00"
    assert schedule[3]["task"]["title"] == "Break"


def test_orchestrator_output(monkeypatch):
    orch = Orchestrator()

    fake_task = {"title": "Demo"}
    fake_model = MagicMock()
    fake_model.model_dump.return_value = fake_task

    with (
        patch(
            "packages.core.agents.plan_llm",
            new=AsyncMock(return_value={"tasks": [fake_model]}),
        ),
        patch(
            "packages.proximal.orchestrator.plan_llm",
            new=AsyncMock(return_value={"tasks": [fake_model]}),
        ),
    ):
        result = orch.run_sync("demo goal")

    assert set(result.keys()) == {"plan", "schedule"}
    assert result["plan"][0] == fake_task
    assert isinstance(result["schedule"], list)
