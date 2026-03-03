"""Tests for wellness memory persistence (WP3)."""

import os
import tempfile
from datetime import datetime, timezone, timedelta

import pytest

from packages.core.models import WellnessObservation, WellnessObservationType
from packages.core.wellness_memory import (
    get_observations_for_session,
    get_session_summaries,
    init_wellness_db,
    store_observation,
)


@pytest.fixture
async def db_path():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    await init_wellness_db(db_path=path)
    yield path
    os.unlink(path)


class TestWellnessMemory:
    async def test_store_and_retrieve(self, db_path):
        obs = WellnessObservation(
            user_id="test",
            session_id="sess1",
            observation_type=WellnessObservationType.session_start,
            data={"goal": "test goal"},
        )
        await store_observation(obs, db_path=db_path)

        results = await get_observations_for_session("sess1", db_path=db_path)
        assert len(results) == 1
        assert results[0].session_id == "sess1"
        assert results[0].observation_type == WellnessObservationType.session_start

    async def test_multiple_observations(self, db_path):
        now = datetime.now(timezone.utc)

        for i in range(5):
            obs = WellnessObservation(
                user_id="test",
                session_id="sess1",
                observation_type=WellnessObservationType.task_completed,
                data={"task": f"task_{i}"},
                timestamp=now + timedelta(minutes=i),
            )
            await store_observation(obs, db_path=db_path)

        results = await get_observations_for_session("sess1", db_path=db_path)
        assert len(results) == 5

    async def test_session_summaries(self, db_path):
        now = datetime.now(timezone.utc)

        # session 1: started, 2 tasks, 1 break, ended
        await store_observation(
            WellnessObservation(
                user_id="test",
                session_id="s1",
                observation_type=WellnessObservationType.session_start,
                timestamp=now,
            ),
            db_path=db_path,
        )
        await store_observation(
            WellnessObservation(
                user_id="test",
                session_id="s1",
                observation_type=WellnessObservationType.task_completed,
                timestamp=now + timedelta(minutes=30),
            ),
            db_path=db_path,
        )
        await store_observation(
            WellnessObservation(
                user_id="test",
                session_id="s1",
                observation_type=WellnessObservationType.break_taken,
                timestamp=now + timedelta(minutes=35),
            ),
            db_path=db_path,
        )
        await store_observation(
            WellnessObservation(
                user_id="test",
                session_id="s1",
                observation_type=WellnessObservationType.task_completed,
                timestamp=now + timedelta(minutes=60),
            ),
            db_path=db_path,
        )
        await store_observation(
            WellnessObservation(
                user_id="test",
                session_id="s1",
                observation_type=WellnessObservationType.session_end,
                timestamp=now + timedelta(minutes=90),
            ),
            db_path=db_path,
        )

        summaries = await get_session_summaries(user_id="test", db_path=db_path)
        assert len(summaries) == 1
        s = summaries[0]
        assert s.session_id == "s1"
        assert s.tasks_completed == 2
        assert s.breaks_taken == 1
        assert s.duration_hours > 0

    async def test_empty_db(self, db_path):
        summaries = await get_session_summaries(user_id="test", db_path=db_path)
        assert summaries == []
