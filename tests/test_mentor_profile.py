"""Tests for Mentor profile-aware encouragement (Phase 1.4).

Verifies that MentorAgent adapts its output based on the user's
tone, celebration_style, and verbosity preferences from UserProfile.
"""

from __future__ import annotations

from packages.core.agents.mentor import MentorAgent
from packages.core.collaboration.context import SharedContext
from packages.core.models import UserProfile

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_context(goal="Test goal", **profile_kwargs):
    profile = UserProfile(**profile_kwargs)
    return SharedContext(goal=goal, user_profile=profile)


# ---------------------------------------------------------------------------
# celebration_style tests
# ---------------------------------------------------------------------------


async def test_celebration_style_quiet():
    agent = MentorAgent()
    ctx = _make_context(goal="Clean desk", celebration_style="quiet")
    result = await agent.run(ctx)

    # quiet style produces understated output
    assert "Clean desk" in result
    assert "!" not in result or result.count("!") == 0


async def test_celebration_style_enthusiastic():
    agent = MentorAgent()
    ctx = _make_context(
        goal="Ship feature",
        celebration_style="enthusiastic",
        tone="warm",
    )
    result = await agent.run(ctx)

    # enthusiastic produces energetic output with exclamation
    assert "Ship feature" in result
    assert "!" in result or "great" in result.lower()


async def test_celebration_style_data_driven():
    agent = MentorAgent()
    ctx = _make_context(
        goal="Write report",
        celebration_style="data-driven",
    )
    result = await agent.run(ctx)

    # data-driven mentions progress/metrics language
    assert "Write report" in result
    assert "progress" in result.lower() or "update" in result.lower()


# ---------------------------------------------------------------------------
# verbosity tests
# ---------------------------------------------------------------------------


async def test_verbosity_minimal():
    agent = MentorAgent()
    ctx = _make_context(
        goal="Quick task",
        verbosity="minimal",
        tone="direct",
    )
    result = await agent.run(ctx)

    # minimal output is one short sentence — count sentence-ending periods
    sentences = [s.strip() for s in result.split(".") if s.strip()]
    assert len(sentences) <= 2


async def test_verbosity_detailed():
    agent = MentorAgent()
    ctx_medium = _make_context(
        goal="Big project",
        verbosity="medium",
        tone="warm",
    )
    ctx_detailed = _make_context(
        goal="Big project",
        verbosity="detailed",
        tone="warm",
    )
    medium_result = await agent.run(ctx_medium)
    detailed_result = await agent.run(ctx_detailed)

    # detailed output should be longer than medium
    assert len(detailed_result) > len(medium_result)


# ---------------------------------------------------------------------------
# tone tests
# ---------------------------------------------------------------------------


async def test_tone_direct():
    agent = MentorAgent()
    ctx = _make_context(goal="Fix bug", tone="direct")
    result = await agent.run(ctx)

    # direct tone is brief and factual — no exclamation marks
    assert "Fix bug" in result
    assert "!" not in result


async def test_tone_playful():
    agent = MentorAgent()
    ctx = _make_context(goal="Learn piano", tone="playful")
    result = await agent.run(ctx)

    # playful tone includes lighthearted language
    assert "Learn piano" in result
    assert "nice" in result.lower() or "!" in result


# ---------------------------------------------------------------------------
# overwhelm + tone
# ---------------------------------------------------------------------------


async def test_overwhelm_adapts_to_tone():
    agent = MentorAgent()

    # warm (default) — should contain empathetic language
    ctx_warm = _make_context(goal="Study", tone="warm")
    ctx_warm.set_signal("overwhelm_detected", True)
    warm_result = await agent.run(ctx_warm)
    assert "feels like a lot" in warm_result.lower()

    # professional — factual language
    ctx_pro = _make_context(goal="Study", tone="professional")
    ctx_pro.set_signal("overwhelm_detected", True)
    pro_result = await agent.run(ctx_pro)
    assert "threshold" in pro_result.lower() or "recommended" in pro_result.lower()

    # direct — brief
    ctx_direct = _make_context(goal="Study", tone="direct")
    ctx_direct.set_signal("overwhelm_detected", True)
    direct_result = await agent.run(ctx_direct)
    assert "pick one" in direct_result.lower() or "too many" in direct_result.lower()

    # playful — lighthearted
    ctx_play = _make_context(goal="Study", tone="playful")
    ctx_play.set_signal("overwhelm_detected", True)
    play_result = await agent.run(ctx_play)
    assert "whoa" in play_result.lower() or "bite-sized" in play_result.lower()


# ---------------------------------------------------------------------------
# backward compatibility
# ---------------------------------------------------------------------------


async def test_default_profile_backward_compat():
    agent = MentorAgent()
    # default UserProfile: tone="warm", celebration_style="quiet", verbosity="medium"
    ctx = _make_context(goal="Default goal")
    result = await agent.run(ctx)

    # should still include the goal and produce a valid string
    assert "Default goal" in result
    assert isinstance(result, str)
    assert len(result) > 0


def test_motivate_method_unchanged():
    agent = MentorAgent()
    result = agent.motivate("Old goal")

    # the old motivate() method should still return the template string
    assert result == "You can achieve 'Old goal' if you tackle it step by step!"
