
from packages.core.agents.guardian import GuardianAgent
from packages.core.agents.mentor import MentorAgent
from packages.core.agents.scribe import ScribeAgent
from packages.core.agents.liaison import LiaisonAgent
from packages.core.agents.focusbuddy import FocusBuddyAgent


def test_guardian_adds_breaks():
    agent = GuardianAgent()
    tasks = [{"title": f"T{i}"} for i in range(5)]
    result = agent.add_nudges(tasks)
    assert len(result) > len(tasks)
    assert any(t.get("title") == "Take a short break" for t in result)


def test_mentor_motivates():
    agent = MentorAgent()
    msg = agent.motivate("Finish project")
    assert "Finish project" in msg


def test_scribe_records(monkeypatch):
    from unittest.mock import AsyncMock
    agent = ScribeAgent()
    mock_store = AsyncMock()
    monkeypatch.setattr(
        "packages.core.agents.scribe.memory.store", mock_store
    )
    plan = [{"title": "Task"}]
    agent.record_plan(plan)
    assert mock_store.called


def test_liaison_message():
    agent = LiaisonAgent()
    msg = agent.draft_message_sync("Goal")
    assert "Goal" in msg


def test_focusbuddy_sessions():
    agent = FocusBuddyAgent()
    tasks = [{"title": "A"}, {"title": "B"}]
    sessions = agent.create_sessions(tasks)
    assert len(sessions) == 2
    assert sessions[0]["duration_min"] == 25
