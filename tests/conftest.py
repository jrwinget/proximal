import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

os.environ.setdefault("SKIP_WEAVIATE_CONNECTION", "1")
os.environ.setdefault("SKIP_DB_CONNECTION", "1")


def _make_litellm_response(content: str = "[]") -> MagicMock:
    """Build a mock litellm response with the given content string."""
    message = MagicMock()
    message.content = content
    message.tool_calls = None
    choice = MagicMock()
    choice.message = message
    response = MagicMock()
    response.choices = [choice]
    return response


@pytest.fixture(scope="session", autouse=True)
def mock_env_settings():
    """Mock environment settings for testing."""

    # test environment variables
    env_vars = {
        "PROVIDER_NAME": "ollama",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "llama3",
        "OPENAI_API_KEY": "sk-test-key",
        "OPENAI_MODEL": "gpt-4o-mini",
        "ANTHROPIC_API_KEY": "sk-ant-test-key",
        "ANTHROPIC_MODEL": "claude-3-haiku",
        "SKIP_WEAVIATE_CONNECTION": "1",
        "SKIP_DB_CONNECTION": "1",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        yield


@pytest.fixture(autouse=True)
def mock_litellm(monkeypatch):
    """Prevent real LLM calls in all tests by default.

    Returns a mock litellm response object with .choices[0].message.content
    so that router.chat can parse it properly.
    """
    mock = AsyncMock(return_value=_make_litellm_response("[]"))
    monkeypatch.setattr("litellm.acompletion", mock)
    return mock
