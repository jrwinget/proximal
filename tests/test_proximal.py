import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from packages.core.agents import AGENT_REGISTRY
from packages.core.agents.chronos import ChronosAgent
from packages.core.agents.guardian import GuardianAgent
from packages.core.agents.mentor import MentorAgent
from packages.core.agents.scribe import ScribeAgent
from packages.core.agents.liaison import LiaisonAgent
from packages.core.agents.focusbuddy import FocusBuddyAgent
from packages.core.orchestrator import Orchestrator


def test_agent_registration():
    """All core agents should be registered."""
    assert AGENT_REGISTRY.get("chronos") is ChronosAgent
    assert AGENT_REGISTRY.get("guardian") is GuardianAgent
    assert AGENT_REGISTRY.get("mentor") is MentorAgent
    assert AGENT_REGISTRY.get("scribe") is ScribeAgent
    assert AGENT_REGISTRY.get("liaison") is LiaisonAgent
    assert AGENT_REGISTRY.get("focusbuddy") is FocusBuddyAgent


def test_chronos_schedule():
    agent = ChronosAgent()
    tasks = [{"title": f"Task {i}"} for i in range(5)]
    schedule = agent.create_schedule(tasks)
    # expect break after third task
    assert len(schedule) == 6
    assert schedule[0]["start"] == "09:00"
    assert schedule[0]["end"] == "10:00"
    assert schedule[3]["task"]["title"] == "Break"

    @patch("packages.core.integrations.automatisch.httpx.post")
    def test_chronos_triggers_automatisch(mock_post):
        mock_post.return_value = MagicMock(
            status_code=200, raise_for_status=lambda: None
        )
        with patch.dict(os.environ, {"AUTOMATISCH_URL": "http://auto"}):
            agent = ChronosAgent()
            tasks = [{"title": "Task"}]
            schedule = agent.create_schedule(tasks)
            mock_post.assert_called_once()
            assert schedule[0]["task"]["title"] == "Task"


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
            "packages.core.orchestrator.plan_llm",
            new=AsyncMock(return_value={"tasks": [fake_model]}),
        ),
        patch(
            "packages.core.agents.chronos.ChronosAgent.create_schedule",
            return_value=[{"task": fake_task}],
        ),
        patch(
            "packages.core.agents.guardian.GuardianAgent.add_nudges",
            return_value=[fake_task],
        ),
        patch("packages.core.agents.mentor.MentorAgent.motivate", return_value="m"),
        patch(
            "packages.core.agents.scribe.ScribeAgent.record_plan", return_value="ok"
        ),
        patch(
            "packages.core.agents.liaison.LiaisonAgent.draft_message",
            return_value="msg",
        ),
        patch(
            "packages.core.agents.focusbuddy.FocusBuddyAgent.create_sessions",
            return_value=[{"session": 1}],
        ),
    ):
        result = orch.run_sync("demo goal")

    expected = {
        "plan",
        "schedule",
        "chronos",
        "guardian",
        "mentor",
        "scribe",
        "liaison",
        "focusbuddy",
    }

    assert set(result.keys()).issuperset(expected)
    assert result["plan"][0] == fake_task
    assert isinstance(result["schedule"], list)
