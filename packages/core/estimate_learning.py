"""Estimate learning — tracks actual vs estimated task durations.

Records task timing data to SQLite and computes estimate bias corrections.
Follows the lazy-init pattern from memory.py.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
from pydantic import BaseModel, Field
from uuid import uuid4


# module-level state for lazy init
_db_path: str | None = None
_initialized: bool = False


def _should_skip() -> bool:
    return bool(
        os.getenv("SKIP_DB_CONNECTION") or os.getenv("SKIP_WEAVIATE_CONNECTION")
    )


def _get_db_path() -> str:
    global _db_path
    if _db_path is not None:
        return _db_path
    default = str(Path.home() / ".proximal" / "proximal.db")
    _db_path = default
    return _db_path


async def _ensure_initialized() -> None:
    global _initialized
    if not _initialized and not _should_skip():
        await init_estimate_db()


class TaskTimingRecord(BaseModel):
    """A record of estimated vs actual task duration."""

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    user_id: str = "default"
    session_id: str = ""
    task_title: str = ""
    task_category: str = "general"
    estimated_hours: float = 1.0
    actual_hours: float = 1.0
    ratio: float = 1.0
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class EstimateBias(BaseModel):
    """Computed estimate bias for a user or category."""

    user_id: str = "default"
    category: str = "general"
    avg_ratio: float = 1.0
    sample_count: int = 0
    correction_factor: float = 1.0


async def init_estimate_db(db_path: str | None = None) -> None:
    """Create scheduling_patterns table if it does not exist."""
    global _initialized
    path = db_path or _get_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS scheduling_patterns (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                task_title TEXT NOT NULL,
                task_category TEXT NOT NULL,
                estimated_hours REAL NOT NULL,
                actual_hours REAL NOT NULL,
                ratio REAL NOT NULL,
                recorded_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sched_user_cat
            ON scheduling_patterns(user_id, task_category)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_sched_user_time
            ON scheduling_patterns(user_id, recorded_at)
            """
        )
        await db.commit()

    _initialized = True


async def record_task_timing(
    record: TaskTimingRecord,
    db_path: str | None = None,
) -> None:
    """Persist a task timing record."""
    if _should_skip() and db_path is None:
        return
    if db_path is None:
        await _ensure_initialized()

    path = db_path or _get_db_path()
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO scheduling_patterns
            (id, user_id, session_id, task_title, task_category,
             estimated_hours, actual_hours, ratio, recorded_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.user_id,
                record.session_id,
                record.task_title,
                record.task_category,
                record.estimated_hours,
                record.actual_hours,
                record.ratio,
                record.recorded_at.isoformat(),
                now,
            ),
        )
        await db.commit()


async def get_estimate_bias(
    user_id: str = "default",
    category: str | None = None,
    db_path: str | None = None,
) -> EstimateBias:
    """Compute the estimate bias for a user, optionally filtered by category.

    Parameters
    ----------
    user_id : str
        The user to query.
    category : str or None
        Optional task category filter.
    db_path : str or None
        Override path for testing.

    Returns
    -------
    EstimateBias
        Computed bias with correction factor.
    """
    if _should_skip() and db_path is None:
        return EstimateBias(user_id=user_id, category=category or "general")
    if db_path is None:
        await _ensure_initialized()

    path = db_path or _get_db_path()

    async with aiosqlite.connect(path) as db:
        if category:
            cursor = await db.execute(
                """
                SELECT AVG(ratio) as avg_ratio, COUNT(*) as cnt
                FROM scheduling_patterns
                WHERE user_id = ? AND task_category = ?
                """,
                (user_id, category),
            )
        else:
            cursor = await db.execute(
                """
                SELECT AVG(ratio) as avg_ratio, COUNT(*) as cnt
                FROM scheduling_patterns
                WHERE user_id = ?
                """,
                (user_id,),
            )

        row = await cursor.fetchone()

    avg_ratio = row[0] if row and row[0] is not None else 1.0
    count = row[1] if row else 0

    # correction factor: if tasks typically take 1.5x longer, multiply estimates by 1.5
    correction = avg_ratio if count >= 3 else 1.0

    return EstimateBias(
        user_id=user_id,
        category=category or "general",
        avg_ratio=round(avg_ratio, 2),
        sample_count=count,
        correction_factor=round(correction, 2),
    )


def apply_estimate_correction(estimated_hours: float, bias: EstimateBias) -> float:
    """Apply the learned correction factor to an estimate.

    Parameters
    ----------
    estimated_hours : float
        The original estimate.
    bias : EstimateBias
        The computed bias.

    Returns
    -------
    float
        Corrected estimate.
    """
    return round(estimated_hours * bias.correction_factor, 1)
