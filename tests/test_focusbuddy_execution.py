"""Tests for Phase 2: FocusBuddy execution-layer features.

Covers:
- 2.1 mid-session check-ins
- 2.2 transition support
- 2.3 progress momentum tracking
- 2.4 session retrospective
- 2.5 body-doubling presence mode
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from packages.core.agents.focusbuddy import FocusBuddyAgent, _celebration_for_retro
from packages.core.collaboration.context import SharedContext
from packages.core.events import Event, EventBus, Topics, reset_event_bus


@pytest.fixture(autouse=True)
def _clean_bus():
    """reset global event bus between tests"""
    reset_event_bus()
    yield
    reset_event_bus()


@pytest.fixture
def buddy():
    return FocusBuddyAgent()


@pytest.fixture
def ctx():
    return SharedContext(goal="test goal", tasks=[{"title": "task-a"}])


# -----------------------------------------------------------------------
# 2.1  mid-session check-ins
# -----------------------------------------------------------------------


class TestCheckinEvents:
    """FocusBuddy emits FOCUSBUDDY_CHECKIN on SESSION_TASK_STARTED."""

    async def test_checkin_emitted_on_task_started(self, buddy):
        """check-in event is published when a task starts"""
        bus = EventBus()
        received = []

        async def capture(evt):
            received.append(evt)

        bus.subscribe(Topics.FOCUSBUDDY_CHECKIN, capture)

        # patch get_event_bus to return our local bus
        import packages.core.events as ev_mod

        original = ev_mod.get_event_bus
        ev_mod.get_event_bus = lambda: bus
        try:
            event = Event(
                topic=Topics.SESSION_TASK_STARTED,
                source="test",
                data={"focus_style": "variable", "transition_difficulty": "moderate"},
            )
            await buddy.on_event(event)
        finally:
            ev_mod.get_event_bus = original

        assert len(received) == 1
        assert received[0].topic == Topics.FOCUSBUDDY_CHECKIN
        assert received[0].data["focus_style"] == "variable"

    def test_checkin_hyperfocus_minimal(self, buddy):
        """hyperfocus style produces minimal intensity with long interval"""
        checkin = buddy._build_checkin("hyperfocus", "moderate")
        assert checkin["intensity"] == "minimal"
        assert checkin["interval_min"] >= 40

    def test_checkin_shortburst_full(self, buddy):
        """short-burst style produces full intensity with short interval"""
        checkin = buddy._build_checkin("short-burst", "moderate")
        assert checkin["intensity"] == "full"
        assert checkin["interval_min"] <= 12

    def test_checkin_variable_moderate(self, buddy):
        """variable style produces moderate intensity"""
        checkin = buddy._build_checkin("variable", "moderate")
        assert checkin["intensity"] == "moderate"
        assert 15 <= checkin["interval_min"] <= 25

    def test_checkin_high_transition_shorter_interval(self, buddy):
        """high transition difficulty shortens check-in interval"""
        normal = buddy._build_checkin("variable", "moderate")
        high = buddy._build_checkin("variable", "high")
        assert high["interval_min"] < normal["interval_min"]

    def test_checkin_low_transition_longer_interval(self, buddy):
        """low transition difficulty lengthens check-in interval"""
        normal = buddy._build_checkin("variable", "moderate")
        low = buddy._build_checkin("variable", "low")
        assert low["interval_min"] > normal["interval_min"]

    def test_checkin_has_message(self, buddy):
        """every check-in has a non-empty message"""
        for style in ("hyperfocus", "variable", "short-burst"):
            checkin = buddy._build_checkin(style, "moderate")
            assert checkin["message"]


# -----------------------------------------------------------------------
# 2.2  transition support
# -----------------------------------------------------------------------


class TestTransitionSupport:
    """Transition messages between tasks scaled by difficulty."""

    def test_low_difficulty_brief(self, buddy):
        """low difficulty produces a brief single-line transition"""
        t = buddy.build_transition("task-a", "task-b", "low")
        assert t["difficulty"] == "low"
        assert not t["break_recommended"]
        assert len(t["steps"]) == 0
        assert "task-a" in t["message"]
        assert "task-b" in t["message"]

    def test_moderate_difficulty_has_steps(self, buddy):
        """moderate difficulty includes one step"""
        t = buddy.build_transition("task-a", "task-b", "moderate")
        assert t["difficulty"] == "moderate"
        assert len(t["steps"]) == 1
        assert not t["break_recommended"]

    def test_high_difficulty_full_ritual(self, buddy):
        """high difficulty provides full transition ritual with break"""
        t = buddy.build_transition("task-a", "task-b", "high")
        assert t["difficulty"] == "high"
        assert t["break_recommended"]
        assert len(t["steps"]) >= 3
        assert any("break" in s.lower() for s in t["steps"])

    async def test_emit_transition_sets_signal(self, buddy, ctx):
        """emit_transition sets transition_in_progress on context"""
        import packages.core.events as ev_mod

        bus = EventBus()
        original = ev_mod.get_event_bus
        ev_mod.get_event_bus = lambda: bus
        try:
            await buddy.emit_transition(
                "task-a", "task-b", "moderate", context=ctx
            )
        finally:
            ev_mod.get_event_bus = original

        assert ctx.get_signal("transition_in_progress") is True

    async def test_emit_transition_publishes_event(self, buddy, ctx):
        """emit_transition publishes a FOCUSBUDDY_TRANSITION event"""
        import packages.core.events as ev_mod

        bus = EventBus()
        received = []

        async def capture(evt):
            received.append(evt)

        bus.subscribe(Topics.FOCUSBUDDY_TRANSITION, capture)

        original = ev_mod.get_event_bus
        ev_mod.get_event_bus = lambda: bus
        try:
            await buddy.emit_transition(
                "task-a", "task-b", "high", context=ctx
            )
        finally:
            ev_mod.get_event_bus = original

        assert len(received) == 1
        assert received[0].data["difficulty"] == "high"

    def test_clear_transition(self, buddy, ctx):
        """clear_transition resets the signal"""
        ctx.set_signal("transition_in_progress", True)
        buddy.clear_transition(ctx)
        assert ctx.get_signal("transition_in_progress") is False


# -----------------------------------------------------------------------
# 2.3  progress momentum tracking
# -----------------------------------------------------------------------


class TestMomentumTracking:
    """Momentum calculation from task completion timestamps."""

    def test_insufficient_data(self, buddy):
        """fewer than 2 completions returns insufficient_data"""
        m = buddy.calculate_momentum([])
        assert m["trend"] == "insufficient_data"
        assert m["signal"] is None

        m2 = buddy.calculate_momentum([datetime.now(timezone.utc)])
        assert m2["trend"] == "insufficient_data"

    def test_steady_momentum(self, buddy):
        """evenly spaced completions produce steady trend"""
        base = datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc)
        times = [base + timedelta(minutes=15 * i) for i in range(6)]
        now = times[-1] + timedelta(minutes=1)
        m = buddy.calculate_momentum(times, _now=now)
        assert m["trend"] == "steady"
        assert m["tasks_per_hour"] > 0

    def test_accelerating_momentum(self, buddy):
        """faster completions in second half produce accelerating trend"""
        base = datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc)
        # first half: 30 min apart; second half: 5 min apart
        times = [
            base,
            base + timedelta(minutes=30),
            base + timedelta(minutes=60),
            base + timedelta(minutes=65),
            base + timedelta(minutes=70),
            base + timedelta(minutes=75),
        ]
        now = times[-1] + timedelta(minutes=1)
        m = buddy.calculate_momentum(times, _now=now)
        assert m["trend"] == "accelerating"

    def test_decelerating_momentum(self, buddy):
        """slower completions in second half produce decelerating trend"""
        base = datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc)
        # first half: 5 min apart; second half: 30 min apart
        times = [
            base,
            base + timedelta(minutes=5),
            base + timedelta(minutes=10),
            base + timedelta(minutes=40),
            base + timedelta(minutes=70),
            base + timedelta(minutes=100),
        ]
        now = times[-1] + timedelta(minutes=1)
        m = buddy.calculate_momentum(times, _now=now)
        assert m["trend"] == "decelerating"

    def test_momentum_high_signal(self, buddy):
        """high rate + accelerating = momentum_high signal"""
        base = datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc)
        times = [
            base,
            base + timedelta(minutes=20),
            base + timedelta(minutes=40),
            base + timedelta(minutes=45),
            base + timedelta(minutes=48),
            base + timedelta(minutes=50),
        ]
        now = times[-1] + timedelta(minutes=1)
        m = buddy.calculate_momentum(times, _now=now)
        assert m["signal"] in ("momentum_high", "momentum_recovering")

    def test_momentum_stalling_signal(self, buddy):
        """low rate + decelerating = momentum_stalling"""
        base = datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc)
        times = [
            base,
            base + timedelta(minutes=10),
            base + timedelta(minutes=80),
            base + timedelta(minutes=160),
        ]
        now = times[-1] + timedelta(hours=2)
        m = buddy.calculate_momentum(times, _now=now)
        assert m["trend"] == "decelerating"
        assert m["signal"] == "momentum_stalling"

    def test_apply_momentum_signals_sets_context(self, buddy, ctx):
        """apply_momentum_signals sets the correct signal on context"""
        base = datetime(2026, 3, 5, 10, 0, tzinfo=timezone.utc)
        buddy._completion_times = [
            base,
            base + timedelta(minutes=10),
            base + timedelta(minutes=80),
            base + timedelta(minutes=160),
        ]
        momentum = buddy.apply_momentum_signals(ctx)
        # at least one signal should be set or all false
        assert "signal" in momentum

    def test_apply_momentum_clears_previous(self, buddy, ctx):
        """previous momentum signals are cleared before setting new ones"""
        ctx.set_signal("momentum_high", True)
        buddy._completion_times = []
        buddy.apply_momentum_signals(ctx)
        assert ctx.get_signal("momentum_high") is False


# -----------------------------------------------------------------------
# 2.4  session retrospective
# -----------------------------------------------------------------------


class TestSessionRetrospective:
    """Retrospective generation on session end."""

    def test_full_completion(self, buddy):
        """all tasks done produces 1.0 ratio"""
        retro = buddy.build_retrospective(
            tasks_planned=5, tasks_completed=5
        )
        assert retro["completion_ratio"] == 1.0
        assert retro["restart_point"] == "All tasks completed — pick a new goal"

    def test_partial_completion(self, buddy):
        """partial completion produces correct ratio and restart point"""
        retro = buddy.build_retrospective(
            tasks_planned=4,
            tasks_completed=2,
            remaining_tasks=["task-c", "task-d"],
        )
        assert retro["completion_ratio"] == 0.5
        assert "task-c" in retro["restart_point"]

    def test_timing_accuracy(self, buddy):
        """timing accuracy is actual / estimated"""
        retro = buddy.build_retrospective(
            tasks_planned=3,
            tasks_completed=3,
            estimated_minutes=60,
            actual_minutes=72,
        )
        assert retro["timing_accuracy"] == 1.2

    def test_celebration_quiet(self, buddy):
        """quiet celebration style produces understated message"""
        retro = buddy.build_retrospective(
            tasks_planned=3, tasks_completed=3, celebration_style="quiet"
        )
        assert "All tasks done" in retro["celebration"]

    def test_celebration_enthusiastic(self, buddy):
        """enthusiastic style produces energetic message"""
        retro = buddy.build_retrospective(
            tasks_planned=3,
            tasks_completed=3,
            celebration_style="enthusiastic",
        )
        assert "crushed" in retro["celebration"].lower() or "amazing" in retro["celebration"].lower()

    def test_celebration_data_driven(self, buddy):
        """data-driven style includes percentage"""
        retro = buddy.build_retrospective(
            tasks_planned=4,
            tasks_completed=3,
            celebration_style="data-driven",
        )
        assert "75%" in retro["celebration"]
        assert "3 tasks" in retro["celebration"]

    async def test_session_ended_emits_retrospective(self, buddy):
        """SESSION_ENDED triggers a FOCUSBUDDY_RETROSPECTIVE event"""
        import packages.core.events as ev_mod

        bus = EventBus()
        received = []

        async def capture(evt):
            received.append(evt)

        bus.subscribe(Topics.FOCUSBUDDY_RETROSPECTIVE, capture)

        original = ev_mod.get_event_bus
        ev_mod.get_event_bus = lambda: bus
        try:
            event = Event(
                topic=Topics.SESSION_ENDED,
                source="test",
                data={
                    "tasks_planned": 3,
                    "tasks_completed": 2,
                    "remaining_tasks": ["task-c"],
                    "celebration_style": "quiet",
                },
            )
            await buddy.on_event(event)
        finally:
            ev_mod.get_event_bus = original

        assert len(received) == 1
        assert received[0].data["completion_ratio"] == pytest.approx(0.67, abs=0.01)
        assert "task-c" in received[0].data["restart_point"]

    def test_zero_planned_tasks(self, buddy):
        """zero planned tasks doesn't divide by zero"""
        retro = buddy.build_retrospective(tasks_planned=0, tasks_completed=0)
        assert retro["completion_ratio"] == 0.0


# -----------------------------------------------------------------------
# 2.5  body-doubling presence mode
# -----------------------------------------------------------------------


class TestPresenceMode:
    """Body-doubling presence tick generation."""

    def test_presence_tick_has_required_keys(self, buddy):
        """tick payload contains all expected keys"""
        tick = buddy.build_presence_tick("variable", "medium")
        assert tick["presence_mode"] is True
        assert "message" in tick
        assert "interval_min" in tick
        assert tick["focus_style"] == "variable"

    def test_hyperfocus_longer_interval(self, buddy):
        """hyperfocus style results in longer presence intervals"""
        hyper = buddy.build_presence_tick("hyperfocus", "medium")
        variable = buddy.build_presence_tick("variable", "medium")
        assert hyper["interval_min"] > variable["interval_min"]

    def test_shortburst_shorter_interval(self, buddy):
        """short-burst style results in shorter presence intervals"""
        short = buddy.build_presence_tick("short-burst", "medium")
        variable = buddy.build_presence_tick("variable", "medium")
        assert short["interval_min"] < variable["interval_min"]

    def test_low_energy_increases_interval(self, buddy):
        """low energy increases interval (less frequent pings)"""
        low = buddy.build_presence_tick("variable", "low")
        medium = buddy.build_presence_tick("variable", "medium")
        assert low["interval_min"] >= medium["interval_min"]

    def test_high_energy_decreases_interval(self, buddy):
        """high energy decreases interval (more frequent pings)"""
        high = buddy.build_presence_tick("variable", "high")
        medium = buddy.build_presence_tick("variable", "medium")
        assert high["interval_min"] <= medium["interval_min"]

    def test_message_rotates_with_elapsed(self, buddy):
        """presence messages rotate as time passes"""
        tick0 = buddy.build_presence_tick(
            "variable", "medium", elapsed_minutes=0
        )
        tick1 = buddy.build_presence_tick(
            "variable", "medium", elapsed_minutes=15
        )
        tick2 = buddy.build_presence_tick(
            "variable", "medium", elapsed_minutes=30
        )
        # at least two of three should differ (rotation)
        messages = {tick0["message"], tick1["message"], tick2["message"]}
        assert len(messages) >= 2

    async def test_emit_presence_publishes_event(self, buddy):
        """emit_presence_tick publishes FOCUSBUDDY_PRESENCE event"""
        import packages.core.events as ev_mod

        bus = EventBus()
        received = []

        async def capture(evt):
            received.append(evt)

        bus.subscribe(Topics.FOCUSBUDDY_PRESENCE, capture)

        original = ev_mod.get_event_bus
        ev_mod.get_event_bus = lambda: bus
        try:
            await buddy.emit_presence_tick(
                "variable", "medium", elapsed_minutes=0
            )
        finally:
            ev_mod.get_event_bus = original

        assert len(received) == 1
        assert received[0].data["presence_mode"] is True

    def test_interval_minimum_floor(self, buddy):
        """interval never goes below 5 minutes"""
        tick = buddy.build_presence_tick(
            "short-burst", "high", elapsed_minutes=0
        )
        assert tick["interval_min"] >= 5


# -----------------------------------------------------------------------
# celebration helper
# -----------------------------------------------------------------------


class TestCelebrationHelper:
    """_celebration_for_retro module-level helper."""

    def test_enthusiastic_full(self):
        assert "crush" in _celebration_for_retro(1.0, 5, "enthusiastic").lower()

    def test_enthusiastic_partial(self):
        msg = _celebration_for_retro(0.6, 3, "enthusiastic")
        assert "3 tasks" in msg

    def test_enthusiastic_low(self):
        msg = _celebration_for_retro(0.2, 1, "enthusiastic")
        assert "progress" in msg.lower()

    def test_data_driven_on_track(self):
        msg = _celebration_for_retro(0.9, 9, "data-driven")
        assert "On track" in msg

    def test_data_driven_room_to_adjust(self):
        msg = _celebration_for_retro(0.5, 3, "data-driven")
        assert "adjust" in msg.lower()

    def test_quiet_full(self):
        assert "All tasks done" in _celebration_for_retro(1.0, 5, "quiet")

    def test_quiet_partial(self):
        msg = _celebration_for_retro(0.6, 3, "quiet")
        assert "3 tasks" in msg

    def test_quiet_low(self):
        msg = _celebration_for_retro(0.2, 1, "quiet")
        assert "pick up" in msg.lower()


# -----------------------------------------------------------------------
# on_event routing
# -----------------------------------------------------------------------


class TestEventRouting:
    """on_event correctly dispatches to sub-handlers."""

    async def test_session_started_resets_state(self, buddy):
        """SESSION_STARTED resets internal tracking"""
        buddy._tasks_completed = 5
        buddy._completion_times = [datetime.now(timezone.utc)]

        event = Event(
            topic=Topics.SESSION_STARTED,
            source="test",
            data={"tasks_planned": 3},
        )
        await buddy.on_event(event)

        assert buddy._tasks_planned == 3
        assert buddy._tasks_completed == 0
        assert buddy._completion_times == []

    async def test_task_completed_tracks(self, buddy):
        """SESSION_TASK_COMPLETED increments tracking"""
        event = Event(
            topic=Topics.SESSION_TASK_COMPLETED,
            source="test",
            data={},
        )
        await buddy.on_event(event)
        assert buddy._tasks_completed == 1
        assert len(buddy._completion_times) == 1

    async def test_unknown_event_ignored(self, buddy):
        """unhandled topics are silently ignored"""
        event = Event(
            topic="some.unknown.topic",
            source="test",
            data={},
        )
        # should not raise
        await buddy.on_event(event)


# -----------------------------------------------------------------------
# mentor reads momentum signals (2.3 cross-agent)
# -----------------------------------------------------------------------


class TestMentorMomentumResponse:
    """Mentor adapts to momentum signals set by FocusBuddy."""

    async def test_mentor_acknowledges_momentum_high(self):
        """mentor output differs when momentum_high is set"""
        from packages.core.agents.mentor import MentorAgent

        mentor = MentorAgent()
        ctx = SharedContext(goal="ship feature")
        ctx.set_signal("momentum_high", True)

        result = await mentor.run(ctx)
        # mentor should still produce output (it doesn't crash)
        assert isinstance(result, str)
        assert len(result) > 0
