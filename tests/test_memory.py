"""Tests for SQLite-backed memory module."""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio


@pytest.fixture
def tmp_db(tmp_path):
    """Provide a temporary database path for testing."""
    return str(tmp_path / "test_proximal.db")


@pytest.fixture(autouse=True)
def reset_memory_state():
    """Reset module-level state between tests."""
    import packages.core.memory as mem

    mem._db_path = None
    mem._initialized = False
    yield
    mem._db_path = None
    mem._initialized = False


@pytest_asyncio.fixture
async def initialized_db(tmp_db):
    """Initialize a temporary database for testing.

    Temporarily clears SKIP_DB_CONNECTION and SKIP_WEAVIATE_CONNECTION so
    that store/search/etc. actually hit the database.
    """
    import packages.core.memory as mem

    # save and clear skip flags so operations reach sqlite
    saved = {}
    for key in ("SKIP_DB_CONNECTION", "SKIP_WEAVIATE_CONNECTION"):
        saved[key] = os.environ.pop(key, None)

    mem._db_path = tmp_db
    mem._initialized = False
    await mem.init_db()

    yield tmp_db

    # restore skip flags
    for key, val in saved.items():
        if val is not None:
            os.environ[key] = val


class TestInitDb:
    @pytest.mark.asyncio
    async def test_init_db_creates_tables(self, tmp_db):
        """init_db should create memory and preferences tables."""
        import packages.core.memory as mem

        mem._db_path = tmp_db
        await mem.init_db()

        assert Path(tmp_db).exists()
        assert mem._initialized is True

    @pytest.mark.asyncio
    async def test_init_db_creates_directory(self, tmp_path):
        """init_db should create parent directory if it does not exist."""
        import packages.core.memory as mem

        nested_path = str(tmp_path / "nested" / "dir" / "test.db")
        mem._db_path = nested_path
        await mem.init_db()

        assert Path(nested_path).exists()

    @pytest.mark.asyncio
    async def test_init_db_idempotent(self, tmp_db):
        """Calling init_db multiple times should not fail."""
        import packages.core.memory as mem

        mem._db_path = tmp_db
        await mem.init_db()
        await mem.init_db()
        assert mem._initialized is True


class TestStore:
    @pytest.mark.asyncio
    async def test_store_inserts_record(self, initialized_db):
        """store should insert a record into the memory table."""
        import packages.core.memory as mem

        await mem.store("planner", "test content")

        results = await mem.search("test content")
        assert len(results) >= 1
        assert any(r["content"] == "test content" for r in results)

    @pytest.mark.asyncio
    async def test_store_multiple_records(self, initialized_db):
        """store should handle multiple inserts."""
        import packages.core.memory as mem

        await mem.store("planner", "first entry")
        await mem.store("packager", "second entry")

        results = await mem.search("entry")
        assert len(results) == 2


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_with_fts(self, initialized_db):
        """search should use FTS5 full-text search."""
        import packages.core.memory as mem

        await mem.store("planner", "build a mobile application")
        await mem.store("planner", "design the database schema")
        await mem.store("planner", "write unit tests")

        results = await mem.search("mobile application")
        assert len(results) >= 1
        assert results[0]["content"] == "build a mobile application"

    @pytest.mark.asyncio
    async def test_search_respects_limit(self, initialized_db):
        """search should respect the limit parameter."""
        import packages.core.memory as mem

        for i in range(10):
            await mem.store("planner", f"task number {i}")

        results = await mem.search("task", limit=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_search_returns_empty_for_no_match(self, initialized_db):
        """search should return empty list when nothing matches."""
        import packages.core.memory as mem

        await mem.store("planner", "build a mobile app")

        results = await mem.search("zznonexistentzz")
        assert results == []


class TestPreferences:
    @pytest.mark.asyncio
    async def test_store_and_get_preferences(self, initialized_db):
        """store_preferences and get_preferences should round-trip data."""
        import packages.core.memory as mem

        prefs = {"sprint_length_weeks": 2, "tone": "casual"}
        await mem.store_preferences("user1", prefs)

        result = await mem.get_preferences("user1")
        assert result is not None
        assert result["sprint_length_weeks"] == 2
        assert result["tone"] == "casual"

    @pytest.mark.asyncio
    async def test_get_preferences_returns_none_for_missing(self, initialized_db):
        """get_preferences should return None for nonexistent user."""
        import packages.core.memory as mem

        result = await mem.get_preferences("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_store_preferences_upserts(self, initialized_db):
        """store_preferences should update existing preferences."""
        import packages.core.memory as mem

        await mem.store_preferences("user1", {"tone": "casual"})
        await mem.store_preferences("user1", {"tone": "professional"})

        result = await mem.get_preferences("user1")
        assert result["tone"] == "professional"


class TestConversationHistory:
    @pytest.mark.asyncio
    async def test_store_and_search_conversation(self, initialized_db):
        """store_conversation and get_conversation_history should round-trip."""
        import packages.core.memory as mem

        data = {
            "goal": "build an app",
            "messages": [{"role": "user", "content": "hello"}],
            "final_plan": [{"name": "Sprint 1"}],
        }
        await mem.store_conversation("session1", data)

        results = await mem.get_conversation_history("build an app")
        assert len(results) >= 1
        assert results[0]["goal"] == "build an app"

    @pytest.mark.asyncio
    async def test_get_conversation_history_limit(self, initialized_db):
        """get_conversation_history should respect limit parameter."""
        import packages.core.memory as mem

        for i in range(10):
            await mem.store_conversation(
                f"session{i}", {"goal": f"goal {i}", "messages": []}
            )

        results = await mem.get_conversation_history("goal", limit=3)
        assert len(results) <= 3

    @pytest.mark.asyncio
    async def test_get_conversation_history_empty(self, initialized_db):
        """get_conversation_history should return empty list for no matches."""
        import packages.core.memory as mem

        results = await mem.get_conversation_history("zznonexistentzz")
        assert results == []


class TestSkipDbConnection:
    @pytest.mark.asyncio
    async def test_skip_db_connection_env_var(self, tmp_db):
        """SKIP_DB_CONNECTION should prevent database initialization."""
        import packages.core.memory as mem

        mem._db_path = tmp_db

        with patch.dict(os.environ, {"SKIP_DB_CONNECTION": "1"}):
            await mem.store("planner", "test")
            results = await mem.search("test")
            assert results == []

    @pytest.mark.asyncio
    async def test_skip_weaviate_connection_backward_compat(self, tmp_db):
        """SKIP_WEAVIATE_CONNECTION should also skip db (backward compat)."""
        import packages.core.memory as mem

        mem._db_path = tmp_db

        with patch.dict(os.environ, {"SKIP_WEAVIATE_CONNECTION": "1"}):
            await mem.store("planner", "test")
            results = await mem.search("test")
            assert results == []
