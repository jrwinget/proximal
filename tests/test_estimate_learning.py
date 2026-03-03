"""Tests for estimate learning persistence (WP4)."""

import os
import tempfile

import pytest

from packages.core.estimate_learning import (
    EstimateBias,
    TaskTimingRecord,
    apply_estimate_correction,
    get_estimate_bias,
    init_estimate_db,
    record_task_timing,
)


@pytest.fixture
async def db_path():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        path = f.name
    await init_estimate_db(db_path=path)
    yield path
    os.unlink(path)


class TestEstimateLearning:
    async def test_record_and_query(self, db_path):
        record = TaskTimingRecord(
            user_id="test",
            session_id="s1",
            task_title="Build feature",
            task_category="coding",
            estimated_hours=2.0,
            actual_hours=3.0,
            ratio=1.5,
        )
        await record_task_timing(record, db_path=db_path)

        bias = await get_estimate_bias(user_id="test", db_path=db_path)
        assert bias.sample_count == 1
        assert bias.avg_ratio == 1.5

    async def test_correction_factor_needs_min_samples(self, db_path):
        """Correction factor should be 1.0 until enough samples."""
        record = TaskTimingRecord(
            user_id="test",
            estimated_hours=1.0,
            actual_hours=2.0,
            ratio=2.0,
        )
        await record_task_timing(record, db_path=db_path)

        bias = await get_estimate_bias(user_id="test", db_path=db_path)
        assert bias.correction_factor == 1.0  # not enough samples

    async def test_correction_factor_with_samples(self, db_path):
        """With 3+ samples, correction should reflect actual ratio."""
        for i in range(5):
            await record_task_timing(
                TaskTimingRecord(
                    user_id="test",
                    task_category="coding",
                    estimated_hours=2.0,
                    actual_hours=3.0,
                    ratio=1.5,
                ),
                db_path=db_path,
            )

        bias = await get_estimate_bias(
            user_id="test", category="coding", db_path=db_path
        )
        assert bias.sample_count == 5
        assert bias.correction_factor == 1.5

    async def test_category_filter(self, db_path):
        await record_task_timing(
            TaskTimingRecord(
                user_id="test",
                task_category="coding",
                estimated_hours=1.0,
                actual_hours=2.0,
                ratio=2.0,
            ),
            db_path=db_path,
        )
        await record_task_timing(
            TaskTimingRecord(
                user_id="test",
                task_category="writing",
                estimated_hours=1.0,
                actual_hours=1.0,
                ratio=1.0,
            ),
            db_path=db_path,
        )

        coding = await get_estimate_bias(
            user_id="test", category="coding", db_path=db_path
        )
        writing = await get_estimate_bias(
            user_id="test", category="writing", db_path=db_path
        )

        assert coding.avg_ratio == 2.0
        assert writing.avg_ratio == 1.0

    async def test_empty_db(self, db_path):
        bias = await get_estimate_bias(user_id="test", db_path=db_path)
        assert bias.sample_count == 0
        assert bias.correction_factor == 1.0


class TestApplyCorrection:
    def test_apply(self):
        bias = EstimateBias(correction_factor=1.5)
        assert apply_estimate_correction(2.0, bias) == 3.0

    def test_no_correction(self):
        bias = EstimateBias(correction_factor=1.0)
        assert apply_estimate_correction(2.0, bias) == 2.0
