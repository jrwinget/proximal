"""SQLite-backed persistence for wellness observations.

Follows the lazy-init pattern from memory.py: module-level state,
``_should_skip()`` for test environments, ``_ensure_initialized()``
for transparent database creation on first use.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from .models import WellnessObservation, WellnessSessionSummary

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
    """Lazy-init the wellness tables on first real call."""
    global _initialized
    if not _initialized and not _should_skip():
        await init_wellness_db()


async def init_wellness_db(db_path: str | None = None) -> None:
    """Create wellness_observations table if it does not exist.

    Parameters
    ----------
    db_path : str or None
        Override path for testing with in-memory databases.
    """
    global _initialized
    path = db_path or _get_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS wellness_observations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                observation_type TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wellness_session
            ON wellness_observations(session_id)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wellness_user_time
            ON wellness_observations(user_id, timestamp)
            """
        )
        await db.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_wellness_type
            ON wellness_observations(observation_type)
            """
        )
        await db.commit()

    _initialized = True


async def store_observation(
    observation: WellnessObservation,
    db_path: str | None = None,
) -> None:
    """Persist a wellness observation.

    Parameters
    ----------
    observation : WellnessObservation
        The observation to store.
    db_path : str or None
        Override path for testing.
    """
    if _should_skip() and db_path is None:
        return
    if db_path is None:
        await _ensure_initialized()

    path = db_path or _get_db_path()
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(path) as db:
        await db.execute(
            """
            INSERT INTO wellness_observations
            (id, user_id, session_id, observation_type, data, timestamp, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                observation.id,
                observation.user_id,
                observation.session_id,
                observation.observation_type,
                json.dumps(observation.data),
                observation.timestamp.isoformat(),
                now,
            ),
        )
        await db.commit()


async def get_session_summaries(
    user_id: str = "default",
    limit: int = 30,
    db_path: str | None = None,
) -> list[WellnessSessionSummary]:
    """Build session summaries from stored observations.

    Parameters
    ----------
    user_id : str
        The user to query.
    limit : int
        Maximum number of sessions to return.
    db_path : str or None
        Override path for testing.

    Returns
    -------
    list[WellnessSessionSummary]
        Summaries ordered by most recent first.
    """
    if _should_skip() and db_path is None:
        return []
    if db_path is None:
        await _ensure_initialized()

    path = db_path or _get_db_path()

    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT session_id, observation_type, data, timestamp
            FROM wellness_observations
            WHERE user_id = ?
            ORDER BY timestamp DESC
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()

    # group by session
    sessions: dict[str, dict] = {}
    for row in rows:
        sid = row["session_id"]
        if sid not in sessions:
            sessions[sid] = {
                "session_id": sid,
                "user_id": user_id,
                "started_at": None,
                "ended_at": None,
                "tasks_completed": 0,
                "breaks_taken": 0,
                "breaks_skipped": 0,
                "was_late_session": False,
            }

        s = sessions[sid]
        ts = datetime.fromisoformat(row["timestamp"])
        obs_type = row["observation_type"]

        if obs_type == "session_start":
            s["started_at"] = ts
        elif obs_type == "session_end":
            s["ended_at"] = ts
        elif obs_type == "task_completed":
            s["tasks_completed"] += 1
        elif obs_type == "break_taken":
            s["breaks_taken"] += 1
        elif obs_type == "break_skipped":
            s["breaks_skipped"] += 1
        elif obs_type == "late_session":
            s["was_late_session"] = True

    # compute duration and build models
    summaries = []
    for data in sessions.values():
        duration = 0.0
        if data["started_at"] and data["ended_at"]:
            delta = data["ended_at"] - data["started_at"]
            duration = delta.total_seconds() / 3600.0
        data["duration_hours"] = duration
        summaries.append(WellnessSessionSummary(**data))

    # sort by started_at descending, limit
    summaries.sort(
        key=lambda s: s.started_at or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return summaries[:limit]


async def get_observations_for_session(
    session_id: str,
    db_path: str | None = None,
) -> list[WellnessObservation]:
    """Retrieve all observations for a specific session.

    Parameters
    ----------
    session_id : str
        The session identifier.
    db_path : str or None
        Override path for testing.

    Returns
    -------
    list[WellnessObservation]
        Observations ordered by timestamp.
    """
    if _should_skip() and db_path is None:
        return []
    if db_path is None:
        await _ensure_initialized()

    path = db_path or _get_db_path()

    async with aiosqlite.connect(path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT id, user_id, session_id, observation_type, data, timestamp
            FROM wellness_observations
            WHERE session_id = ?
            ORDER BY timestamp ASC
            """,
            (session_id,),
        )
        rows = await cursor.fetchall()

    return [
        WellnessObservation(
            id=row["id"],
            user_id=row["user_id"],
            session_id=row["session_id"],
            observation_type=row["observation_type"],
            data=json.loads(row["data"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
        )
        for row in rows
    ]
