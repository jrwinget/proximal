"""SQLite-backed memory module replacing Weaviate.

Uses aiosqlite with FTS5 for full-text search. Database is stored at
~/.proximal/proximal.db by default and auto-initializes on first use.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite

# module-level state for lazy init
_db_path: str | None = None
_initialized: bool = False


def _should_skip() -> bool:
    """Check if database operations should be skipped (test env)."""
    return bool(
        os.getenv("SKIP_DB_CONNECTION")
        or os.getenv("SKIP_WEAVIATE_CONNECTION")
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
    """Lazy-init the database on first real call."""
    global _initialized
    if not _initialized and not _should_skip():
        await init_db()


async def init_db() -> None:
    """Create tables if they do not exist.

    Creates the database directory, the memory table with FTS5, a preferences
    table, and a conversation_history table with FTS5.
    """
    global _initialized
    db_path = _get_db_path()

    # create parent directory if needed
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        # main memory table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )

        # fts5 virtual table for memory search
        await db.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
            USING fts5(content, content=memory, content_rowid=id)
            """
        )

        # triggers to keep fts index in sync
        await db.execute(
            """
            CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory BEGIN
                INSERT INTO memory_fts(rowid, content) VALUES (new.id, new.content);
            END
            """
        )

        # preferences table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS preferences (
                user_id TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        # conversation history table
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                goal TEXT,
                messages TEXT,
                final_plan TEXT,
                created_at TEXT NOT NULL
            )
            """
        )

        # fts5 virtual table for conversation search
        await db.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS conversation_fts
            USING fts5(goal, content=conversation_history, content_rowid=id)
            """
        )

        await db.execute(
            """
            CREATE TRIGGER IF NOT EXISTS conversation_ai AFTER INSERT ON conversation_history BEGIN
                INSERT INTO conversation_fts(rowid, goal) VALUES (new.id, new.goal);
            END
            """
        )

        await db.commit()

    _initialized = True


async def store(role: str, content: str) -> None:
    """Insert a memory record.

    Parameters
    ----------
    role : str
        The role label (e.g. "planner", "packager").
    content : str
        The text content to persist.
    """
    if _should_skip():
        return
    await _ensure_initialized()

    db_path = _get_db_path()
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO memory (role, content, created_at) VALUES (?, ?, ?)",
            (role, content, now),
        )
        await db.commit()


async def search(query: str, limit: int = 5) -> list[dict]:
    """Full-text search over memory records.

    Parameters
    ----------
    query : str
        The search query string.
    limit : int
        Maximum number of results to return.

    Returns
    -------
    list[dict]
        Matching records with 'role', 'content', and 'created_at' keys.
    """
    if _should_skip():
        return []
    await _ensure_initialized()

    db_path = _get_db_path()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT m.role, m.content, m.created_at
            FROM memory m
            JOIN memory_fts f ON m.id = f.rowid
            WHERE memory_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
        rows = await cursor.fetchall()
        return [
            {"role": row["role"], "content": row["content"], "created_at": row["created_at"]}
            for row in rows
        ]


async def store_preferences(user_id: str, preferences: dict) -> None:
    """Insert or update user preferences.

    Parameters
    ----------
    user_id : str
        The user identifier.
    preferences : dict
        Preference key-value pairs to store.
    """
    if _should_skip():
        return
    await _ensure_initialized()

    db_path = _get_db_path()
    now = datetime.now(timezone.utc).isoformat()
    data_json = json.dumps(preferences)

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO preferences (user_id, data, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
            """,
            (user_id, data_json, now),
        )
        await db.commit()


async def get_preferences(user_id: str) -> Optional[dict]:
    """Retrieve user preferences.

    Parameters
    ----------
    user_id : str
        The user identifier.

    Returns
    -------
    dict or None
        The preferences dict, or None if not found.
    """
    if _should_skip():
        return None
    await _ensure_initialized()

    db_path = _get_db_path()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT data FROM preferences WHERE user_id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        if row:
            return json.loads(row["data"])
        return None


async def store_conversation(session_id: str, data: dict) -> None:
    """Persist a conversation session to history.

    Parameters
    ----------
    session_id : str
        The session identifier.
    data : dict
        Must contain 'goal'; may contain 'messages' and 'final_plan'.
    """
    if _should_skip():
        return
    await _ensure_initialized()

    db_path = _get_db_path()
    now = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO conversation_history (session_id, goal, messages, final_plan, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                data.get("goal", ""),
                json.dumps(data.get("messages", [])),
                json.dumps(data.get("final_plan")) if data.get("final_plan") else None,
                now,
            ),
        )
        await db.commit()


async def get_conversation_history(query: str, limit: int = 5) -> list[dict]:
    """Search conversation history using full-text search.

    Parameters
    ----------
    query : str
        The search query string.
    limit : int
        Maximum number of results to return.

    Returns
    -------
    list[dict]
        Matching conversations with 'goal', 'messages', and 'plan' keys.
    """
    if _should_skip():
        return []
    await _ensure_initialized()

    db_path = _get_db_path()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """
            SELECT ch.goal, ch.messages, ch.final_plan
            FROM conversation_history ch
            JOIN conversation_fts f ON ch.id = f.rowid
            WHERE conversation_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            results.append(
                {
                    "goal": row["goal"],
                    "messages": json.loads(row["messages"]) if row["messages"] else [],
                    "plan": json.loads(row["final_plan"]) if row["final_plan"] else None,
                }
            )
        return results
