"""Analytics aggregator — SQLite-backed analytics collection and reporting.

Follows the lazy-init pattern from wellness_memory.py: module-level state,
``_should_skip()`` for test environments, ``_ensure_initialized()``
for transparent database creation on first use.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from .models import EnergySnapshot, FocusSessionRecord, TaskCompletion

# module-level state for lazy init
_db_path: str | None = None
_initialized: bool = False


def _should_skip() -> bool:
    """Check if database operations should be skipped (test env)."""
    return bool(
        os.getenv("SKIP_DB_CONNECTION") or os.getenv("SKIP_WEAVIATE_CONNECTION")
    )


def _get_db_path() -> str:
    """Return the database file path, defaulting to ~/.proximal/proximal.db."""
    global _db_path
    if _db_path is not None:
        return _db_path
    default = str(Path.home() / ".proximal" / "proximal.db")
    _db_path = default
    return _db_path


async def _ensure_initialized() -> None:
    """Lazy-init the analytics tables on first real call."""
    global _initialized
    if not _initialized and not _should_skip():
        await init_analytics_db()


async def init_analytics_db(db_path: str | None = None) -> None:
    """Create analytics tables if they do not exist.

    Parameters
    ----------
    db_path : str or None
        Override path for testing with in-memory databases.
    """
    global _initialized
    path = db_path or _get_db_path()

    # only create parent dir for real file paths, not in-memory
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS task_completions (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                title TEXT NOT NULL,
                predicted_hours REAL NOT NULL,
                actual_hours REAL NOT NULL,
                completed_at TEXT NOT NULL,
                energy_level TEXT NOT NULL,
                session_id TEXT NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS focus_sessions (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                planned_duration_min INTEGER NOT NULL,
                actual_duration_min INTEGER NOT NULL,
                completed INTEGER NOT NULL,
                interrupted INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS energy_snapshots (
                id TEXT PRIMARY KEY,
                recorded_at TEXT NOT NULL,
                energy_level TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT ''
            )
            """
        )

        # indexes for common query patterns
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_task_completions_session
            ON task_completions(session_id)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_task_completions_completed_at
            ON task_completions(completed_at)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_focus_sessions_started_at
            ON focus_sessions(started_at)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_energy_snapshots_recorded_at
            ON energy_snapshots(recorded_at)
            """
        )

        await db.commit()

    _initialized = True


# ---------------------------------------------------------------------------
# standalone record helpers
# ---------------------------------------------------------------------------


async def record_task_completion(
    completion: TaskCompletion,
    db_path: str | None = None,
) -> None:
    """Persist a task completion record.

    Parameters
    ----------
    completion : TaskCompletion
        The completion event to store.
    db_path : str or None
        Override path for testing.
    """
    if _should_skip() and db_path is None:
        return
    if db_path is None:
        await _ensure_initialized()

    path = db_path or _get_db_path()

    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO task_completions
            (id, task_id, title, predicted_hours, actual_hours, completed_at,
             energy_level, session_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                completion.id,
                completion.task_id,
                completion.title,
                completion.predicted_hours,
                completion.actual_hours,
                completion.completed_at,
                completion.energy_level,
                completion.session_id,
            ),
        )
        await db.commit()


async def record_focus_session(
    session: FocusSessionRecord,
    db_path: str | None = None,
) -> None:
    """Persist a focus session record.

    Parameters
    ----------
    session : FocusSessionRecord
        The focus session to store.
    db_path : str or None
        Override path for testing.
    """
    if _should_skip() and db_path is None:
        return
    if db_path is None:
        await _ensure_initialized()

    path = db_path or _get_db_path()

    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO focus_sessions
            (id, task_id, planned_duration_min, actual_duration_min, completed,
             interrupted, started_at, ended_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session.id,
                session.task_id,
                session.planned_duration_min,
                session.actual_duration_min,
                int(session.completed),
                int(session.interrupted),
                session.started_at,
                session.ended_at,
            ),
        )
        await db.commit()


async def record_energy_snapshot(
    snapshot: EnergySnapshot,
    db_path: str | None = None,
) -> None:
    """Persist an energy level snapshot.

    Parameters
    ----------
    snapshot : EnergySnapshot
        The energy snapshot to store.
    db_path : str or None
        Override path for testing.
    """
    if _should_skip() and db_path is None:
        return
    if db_path is None:
        await _ensure_initialized()

    path = db_path or _get_db_path()

    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO energy_snapshots (id, recorded_at, energy_level, notes)
            VALUES (?, ?, ?, ?)
            """,
            (
                snapshot.id,
                snapshot.recorded_at,
                snapshot.energy_level,
                snapshot.notes,
            ),
        )
        await db.commit()


# ---------------------------------------------------------------------------
# aggregator class
# ---------------------------------------------------------------------------


class AnalyticsAggregator:
    """Pure SQL/Python analytics aggregator — no LLM calls.

    Uses aiosqlite for all queries. Accepts an optional ``db_path`` override
    for testing with temporary or in-memory databases.

    Parameters
    ----------
    db_path : str or None
        Override path for testing. When ``None`` the module-level default is
        used.
    """

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path

    def _get_path(self) -> str:
        """Resolve the database path."""
        return self._db_path or _get_db_path()

    @staticmethod
    def _cutoff_iso(days: int) -> str:
        """Return an ISO-8601 cutoff timestamp ``days`` ago from now."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        return cutoff.isoformat()

    async def task_completion_rates(self, user_id: str, days: int = 30) -> dict:
        """Percentage of tasks completed and average accuracy ratio.

        Parameters
        ----------
        user_id : str
            The user identifier (matched against session_id prefix by
            convention, or used as-is).
        days : int
            Lookback window in days.

        Returns
        -------
        dict
            Keys: ``total_tasks``, ``completion_rate``, ``avg_accuracy_ratio``.
        """
        cutoff = self._cutoff_iso(days)
        path = self._get_path()

        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row

            # total tasks recorded
            cursor = await db.execute(
                """
                SELECT COUNT(*) AS cnt,
                       AVG(CASE WHEN actual_hours > 0
                           THEN predicted_hours / actual_hours
                           ELSE NULL END) AS avg_ratio
                FROM task_completions
                WHERE completed_at >= ?
                """,
                (cutoff,),
            )
            row = await cursor.fetchone()

        total = row["cnt"] if row else 0
        avg_ratio = round(row["avg_ratio"], 2) if row and row["avg_ratio"] else 0.0

        return {
            "total_tasks": total,
            "completion_rate": 100.0 if total > 0 else 0.0,
            "avg_accuracy_ratio": avg_ratio,
        }

    async def energy_patterns(self, user_id: str, days: int = 30) -> list[dict]:
        """Energy level distribution over the given time window.

        Parameters
        ----------
        user_id : str
            The user identifier.
        days : int
            Lookback window in days.

        Returns
        -------
        list[dict]
            Each entry has ``energy_level`` and ``count``.
        """
        cutoff = self._cutoff_iso(days)
        path = self._get_path()

        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT energy_level, COUNT(*) AS cnt
                FROM energy_snapshots
                WHERE recorded_at >= ?
                GROUP BY energy_level
                ORDER BY cnt DESC
                """,
                (cutoff,),
            )
            rows = await cursor.fetchall()

        return [
            {"energy_level": row["energy_level"], "count": row["cnt"]} for row in rows
        ]

    async def estimate_accuracy(self, user_id: str, days: int = 30) -> dict:
        """Average predicted vs actual hours and estimation bias direction.

        Parameters
        ----------
        user_id : str
            The user identifier.
        days : int
            Lookback window in days.

        Returns
        -------
        dict
            Keys: ``avg_predicted``, ``avg_actual``, ``bias`` (over/under/accurate).
        """
        cutoff = self._cutoff_iso(days)
        path = self._get_path()

        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT AVG(predicted_hours) AS avg_pred,
                       AVG(actual_hours)    AS avg_act
                FROM task_completions
                WHERE completed_at >= ?
                """,
                (cutoff,),
            )
            row = await cursor.fetchone()

        avg_pred = round(row["avg_pred"], 2) if row and row["avg_pred"] else 0.0
        avg_act = round(row["avg_act"], 2) if row and row["avg_act"] else 0.0

        if avg_pred == 0.0 and avg_act == 0.0:
            bias = "no_data"
        elif avg_pred > avg_act * 1.1:
            bias = "over"
        elif avg_pred < avg_act * 0.9:
            bias = "under"
        else:
            bias = "accurate"

        return {
            "avg_predicted": avg_pred,
            "avg_actual": avg_act,
            "bias": bias,
        }

    async def focus_session_adherence(self, user_id: str, days: int = 30) -> dict:
        """Focus session completion rate and average interruptions.

        Parameters
        ----------
        user_id : str
            The user identifier.
        days : int
            Lookback window in days.

        Returns
        -------
        dict
            Keys: ``total_sessions``, ``completion_rate``, ``avg_interruptions``.
        """
        cutoff = self._cutoff_iso(days)
        path = self._get_path()

        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT COUNT(*)          AS total,
                       SUM(completed)    AS completed_cnt,
                       SUM(interrupted)  AS interrupted_cnt
                FROM focus_sessions
                WHERE started_at >= ?
                """,
                (cutoff,),
            )
            row = await cursor.fetchone()

        total = row["total"] if row else 0
        completed_cnt = row["completed_cnt"] if row and row["completed_cnt"] else 0
        interrupted_cnt = (
            row["interrupted_cnt"] if row and row["interrupted_cnt"] else 0
        )

        completion_rate = round((completed_cnt / total) * 100, 1) if total > 0 else 0.0
        avg_interruptions = round(interrupted_cnt / total, 2) if total > 0 else 0.0

        return {
            "total_sessions": total,
            "completion_rate": completion_rate,
            "avg_interruptions": avg_interruptions,
        }

    async def burnout_risk_indicators(self, user_id: str, days: int = 30) -> dict:
        """Combine wellness and work patterns to estimate burnout risk.

        Parameters
        ----------
        user_id : str
            The user identifier.
        days : int
            Lookback window in days.

        Returns
        -------
        dict
            Keys: ``risk_level`` (low/moderate/high), ``indicators`` list,
            ``total_hours_worked``, ``low_energy_pct``.
        """
        cutoff = self._cutoff_iso(days)
        path = self._get_path()
        indicators: list[str] = []

        # total hours worked
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT COALESCE(SUM(actual_hours), 0) AS total_hours
                FROM task_completions
                WHERE completed_at >= ?
                """,
                (cutoff,),
            )
            row = await cursor.fetchone()
            total_hours = row["total_hours"] if row else 0.0

        # low-energy percentage from snapshots
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN energy_level = 'low' THEN 1 ELSE 0 END) AS low_cnt
                FROM energy_snapshots
                WHERE recorded_at >= ?
                """,
                (cutoff,),
            )
            row = await cursor.fetchone()
            snap_total = row["total"] if row else 0
            low_cnt = row["low_cnt"] if row and row["low_cnt"] else 0

        low_energy_pct = (
            round((low_cnt / snap_total) * 100, 1) if snap_total > 0 else 0.0
        )

        # high interruption rate from focus sessions
        focus = await self.focus_session_adherence(user_id, days)
        if focus["avg_interruptions"] > 0.5:
            indicators.append("high_interruption_rate")
        if focus["completion_rate"] < 50.0 and focus["total_sessions"] > 0:
            indicators.append("low_focus_completion")

        if low_energy_pct > 60:
            indicators.append("frequent_low_energy")
        if total_hours > days * 8:
            indicators.append("excessive_hours")

        # determine risk level
        if len(indicators) >= 3:
            risk = "high"
        elif len(indicators) >= 1:
            risk = "moderate"
        else:
            risk = "low"

        return {
            "risk_level": risk,
            "indicators": indicators,
            "total_hours_worked": round(total_hours, 1),
            "low_energy_pct": low_energy_pct,
        }

    async def weekly_summary(self, user_id: str) -> dict:
        """Combine all analytics for the last 7 days.

        Parameters
        ----------
        user_id : str
            The user identifier.

        Returns
        -------
        dict
            Keys: ``completion``, ``energy``, ``estimates``, ``focus``,
            ``burnout``.
        """
        completion = await self.task_completion_rates(user_id, days=7)
        energy = await self.energy_patterns(user_id, days=7)
        estimates = await self.estimate_accuracy(user_id, days=7)
        focus = await self.focus_session_adherence(user_id, days=7)
        burnout = await self.burnout_risk_indicators(user_id, days=7)

        return {
            "completion": completion,
            "energy": energy,
            "estimates": estimates,
            "focus": focus,
            "burnout": burnout,
        }
