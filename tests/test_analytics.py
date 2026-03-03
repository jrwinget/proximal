"""Tests for the analytics module — aggregator, recording, and models."""

import pytest
import pytest_asyncio
import os
from datetime import datetime, timezone
from unittest.mock import patch

from packages.core.analytics.models import (
    EnergySnapshot,
    FocusSessionRecord,
    TaskCompletion,
)
from packages.core.analytics.aggregator import (
    AnalyticsAggregator,
    init_analytics_db,
    record_energy_snapshot,
    record_focus_session,
    record_task_completion,
)
import packages.core.analytics.aggregator as agg_mod


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path for testing."""
    return str(tmp_path / "test_analytics.db")


@pytest.fixture(autouse=True)
def reset_analytics_state():
    """Reset module-level state between tests."""
    agg_mod._db_path = None
    agg_mod._initialized = False
    yield
    agg_mod._db_path = None
    agg_mod._initialized = False


@pytest_asyncio.fixture
async def initialized_db(tmp_db):
    """Initialize a temporary analytics database.

    Temporarily clears SKIP_DB_CONNECTION and SKIP_WEAVIATE_CONNECTION so
    that record/query functions actually hit the database.
    """
    saved = {}
    for key in ("SKIP_DB_CONNECTION", "SKIP_WEAVIATE_CONNECTION"):
        saved[key] = os.environ.pop(key, None)

    agg_mod._db_path = tmp_db
    agg_mod._initialized = False
    await init_analytics_db(tmp_db)

    yield tmp_db

    # restore skip flags
    for key, val in saved.items():
        if val is not None:
            os.environ[key] = val


# ---------------------------------------------------------------------------
# model tests
# ---------------------------------------------------------------------------


class TestModels:
    def test_task_completion_defaults(self):
        """TaskCompletion should auto-generate an 8-char id."""
        tc = TaskCompletion(
            task_id="t1",
            title="Write tests",
            predicted_hours=2.0,
            actual_hours=1.5,
            completed_at="2026-03-01T10:00:00+00:00",
            energy_level="high",
            session_id="s1",
        )
        assert len(tc.id) == 8
        assert tc.task_id == "t1"

    def test_focus_session_defaults(self):
        """FocusSessionRecord should auto-generate an 8-char id."""
        fs = FocusSessionRecord(
            task_id="t1",
            planned_duration_min=25,
            actual_duration_min=20,
            completed=True,
            interrupted=False,
            started_at="2026-03-01T10:00:00+00:00",
        )
        assert len(fs.id) == 8
        assert fs.ended_at is None

    def test_energy_snapshot_defaults(self):
        """EnergySnapshot should auto-generate id and default notes to empty."""
        snap = EnergySnapshot(
            recorded_at="2026-03-01T10:00:00+00:00",
            energy_level="medium",
        )
        assert len(snap.id) == 8
        assert snap.notes == ""


# ---------------------------------------------------------------------------
# record / retrieve tests
# ---------------------------------------------------------------------------


class TestRecordTaskCompletion:
    @pytest.mark.asyncio
    async def test_record_and_query(self, initialized_db):
        """record_task_completion should persist data readable by aggregator."""
        tc = TaskCompletion(
            task_id="t1",
            title="Write unit tests",
            predicted_hours=2.0,
            actual_hours=1.5,
            completed_at=datetime.now(timezone.utc).isoformat(),
            energy_level="high",
            session_id="s1",
        )
        await record_task_completion(tc, db_path=initialized_db)

        agg = AnalyticsAggregator(db_path=initialized_db)
        rates = await agg.task_completion_rates("default", days=30)
        assert rates["total_tasks"] == 1

    @pytest.mark.asyncio
    async def test_record_multiple_completions(self, initialized_db):
        """Multiple completions should all be stored."""
        now = datetime.now(timezone.utc).isoformat()
        for i in range(3):
            tc = TaskCompletion(
                task_id=f"t{i}",
                title=f"Task {i}",
                predicted_hours=float(i + 1),
                actual_hours=float(i + 1),
                completed_at=now,
                energy_level="medium",
                session_id="s1",
            )
            await record_task_completion(tc, db_path=initialized_db)

        agg = AnalyticsAggregator(db_path=initialized_db)
        rates = await agg.task_completion_rates("default", days=30)
        assert rates["total_tasks"] == 3


class TestRecordFocusSession:
    @pytest.mark.asyncio
    async def test_record_focus_session(self, initialized_db):
        """record_focus_session should persist focus session data."""
        fs = FocusSessionRecord(
            task_id="t1",
            planned_duration_min=25,
            actual_duration_min=25,
            completed=True,
            interrupted=False,
            started_at=datetime.now(timezone.utc).isoformat(),
            ended_at=datetime.now(timezone.utc).isoformat(),
        )
        await record_focus_session(fs, db_path=initialized_db)

        agg = AnalyticsAggregator(db_path=initialized_db)
        adherence = await agg.focus_session_adherence("default", days=30)
        assert adherence["total_sessions"] == 1
        assert adherence["completion_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_interrupted_session(self, initialized_db):
        """An interrupted session should be reflected in adherence stats."""
        fs = FocusSessionRecord(
            task_id="t1",
            planned_duration_min=25,
            actual_duration_min=10,
            completed=False,
            interrupted=True,
            started_at=datetime.now(timezone.utc).isoformat(),
        )
        await record_focus_session(fs, db_path=initialized_db)

        agg = AnalyticsAggregator(db_path=initialized_db)
        adherence = await agg.focus_session_adherence("default", days=30)
        assert adherence["completion_rate"] == 0.0
        assert adherence["avg_interruptions"] == 1.0


class TestRecordEnergySnapshot:
    @pytest.mark.asyncio
    async def test_record_energy_snapshot(self, initialized_db):
        """record_energy_snapshot should persist snapshot data."""
        snap = EnergySnapshot(
            recorded_at=datetime.now(timezone.utc).isoformat(),
            energy_level="low",
            notes="feeling tired",
        )
        await record_energy_snapshot(snap, db_path=initialized_db)

        agg = AnalyticsAggregator(db_path=initialized_db)
        patterns = await agg.energy_patterns("default", days=30)
        assert len(patterns) == 1
        assert patterns[0]["energy_level"] == "low"
        assert patterns[0]["count"] == 1

    @pytest.mark.asyncio
    async def test_multiple_energy_levels(self, initialized_db):
        """Multiple snapshots at different levels should be grouped."""
        now = datetime.now(timezone.utc).isoformat()
        for level in ["low", "low", "medium", "high"]:
            snap = EnergySnapshot(
                recorded_at=now,
                energy_level=level,
            )
            await record_energy_snapshot(snap, db_path=initialized_db)

        agg = AnalyticsAggregator(db_path=initialized_db)
        patterns = await agg.energy_patterns("default", days=30)
        levels = {p["energy_level"]: p["count"] for p in patterns}
        assert levels["low"] == 2
        assert levels["medium"] == 1
        assert levels["high"] == 1


# ---------------------------------------------------------------------------
# aggregator tests
# ---------------------------------------------------------------------------


class TestEstimateAccuracy:
    @pytest.mark.asyncio
    async def test_over_estimation(self, initialized_db):
        """Should detect over-estimation bias."""
        now = datetime.now(timezone.utc).isoformat()
        tc = TaskCompletion(
            task_id="t1",
            title="Task 1",
            predicted_hours=5.0,
            actual_hours=2.0,
            completed_at=now,
            energy_level="medium",
            session_id="s1",
        )
        await record_task_completion(tc, db_path=initialized_db)

        agg = AnalyticsAggregator(db_path=initialized_db)
        result = await agg.estimate_accuracy("default", days=30)
        assert result["bias"] == "over"
        assert result["avg_predicted"] == 5.0
        assert result["avg_actual"] == 2.0

    @pytest.mark.asyncio
    async def test_under_estimation(self, initialized_db):
        """Should detect under-estimation bias."""
        now = datetime.now(timezone.utc).isoformat()
        tc = TaskCompletion(
            task_id="t1",
            title="Task 1",
            predicted_hours=1.0,
            actual_hours=5.0,
            completed_at=now,
            energy_level="medium",
            session_id="s1",
        )
        await record_task_completion(tc, db_path=initialized_db)

        agg = AnalyticsAggregator(db_path=initialized_db)
        result = await agg.estimate_accuracy("default", days=30)
        assert result["bias"] == "under"

    @pytest.mark.asyncio
    async def test_accurate_estimation(self, initialized_db):
        """Should detect accurate estimation."""
        now = datetime.now(timezone.utc).isoformat()
        tc = TaskCompletion(
            task_id="t1",
            title="Task 1",
            predicted_hours=3.0,
            actual_hours=3.0,
            completed_at=now,
            energy_level="medium",
            session_id="s1",
        )
        await record_task_completion(tc, db_path=initialized_db)

        agg = AnalyticsAggregator(db_path=initialized_db)
        result = await agg.estimate_accuracy("default", days=30)
        assert result["bias"] == "accurate"

    @pytest.mark.asyncio
    async def test_no_data(self, initialized_db):
        """Should return no_data when there are no completions."""
        agg = AnalyticsAggregator(db_path=initialized_db)
        result = await agg.estimate_accuracy("default", days=30)
        assert result["bias"] == "no_data"


class TestBurnoutRisk:
    @pytest.mark.asyncio
    async def test_low_risk(self, initialized_db):
        """No indicators should yield low risk."""
        agg = AnalyticsAggregator(db_path=initialized_db)
        result = await agg.burnout_risk_indicators("default", days=30)
        assert result["risk_level"] == "low"
        assert result["indicators"] == []

    @pytest.mark.asyncio
    async def test_moderate_risk(self, initialized_db):
        """Frequent low energy should yield at least moderate risk."""
        now = datetime.now(timezone.utc).isoformat()
        # add mostly low energy snapshots
        for _ in range(8):
            snap = EnergySnapshot(recorded_at=now, energy_level="low")
            await record_energy_snapshot(snap, db_path=initialized_db)
        for _ in range(2):
            snap = EnergySnapshot(recorded_at=now, energy_level="high")
            await record_energy_snapshot(snap, db_path=initialized_db)

        agg = AnalyticsAggregator(db_path=initialized_db)
        result = await agg.burnout_risk_indicators("default", days=30)
        assert result["risk_level"] in ("moderate", "high")
        assert "frequent_low_energy" in result["indicators"]


class TestWeeklySummary:
    @pytest.mark.asyncio
    async def test_weekly_summary_combines_data(self, initialized_db):
        """weekly_summary should return all sub-report keys."""
        now = datetime.now(timezone.utc).isoformat()

        # add some task completion data
        tc = TaskCompletion(
            task_id="t1",
            title="Weekly task",
            predicted_hours=3.0,
            actual_hours=2.5,
            completed_at=now,
            energy_level="high",
            session_id="s1",
        )
        await record_task_completion(tc, db_path=initialized_db)

        # add a focus session
        fs = FocusSessionRecord(
            task_id="t1",
            planned_duration_min=25,
            actual_duration_min=25,
            completed=True,
            interrupted=False,
            started_at=now,
        )
        await record_focus_session(fs, db_path=initialized_db)

        # add an energy snapshot
        snap = EnergySnapshot(
            recorded_at=now,
            energy_level="high",
        )
        await record_energy_snapshot(snap, db_path=initialized_db)

        agg = AnalyticsAggregator(db_path=initialized_db)
        summary = await agg.weekly_summary("default")

        assert "completion" in summary
        assert "energy" in summary
        assert "estimates" in summary
        assert "focus" in summary
        assert "burnout" in summary

        assert summary["completion"]["total_tasks"] == 1
        assert summary["focus"]["total_sessions"] == 1
        assert len(summary["energy"]) == 1

    @pytest.mark.asyncio
    async def test_weekly_summary_empty(self, initialized_db):
        """weekly_summary should work with no data."""
        agg = AnalyticsAggregator(db_path=initialized_db)
        summary = await agg.weekly_summary("default")

        assert summary["completion"]["total_tasks"] == 0
        assert summary["energy"] == []
        assert summary["focus"]["total_sessions"] == 0
        assert summary["burnout"]["risk_level"] == "low"


# ---------------------------------------------------------------------------
# skip-env tests
# ---------------------------------------------------------------------------


class TestSkipDbConnection:
    @pytest.mark.asyncio
    async def test_skip_db_prevents_recording(self, tmp_db):
        """SKIP_DB_CONNECTION should prevent record functions from writing."""
        agg_mod._db_path = tmp_db

        with patch.dict(os.environ, {"SKIP_DB_CONNECTION": "1"}):
            tc = TaskCompletion(
                task_id="t1",
                title="Skipped task",
                predicted_hours=1.0,
                actual_hours=1.0,
                completed_at=datetime.now(timezone.utc).isoformat(),
                energy_level="medium",
                session_id="s1",
            )
            # should silently no-op
            await record_task_completion(tc)
