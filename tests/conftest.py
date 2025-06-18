import pytest
import os
import sys
from pathlib import Path
from unittest.mock import patch

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture(scope="session", autouse=True)
def mock_env_settings():
    """Mock environment settings for testing."""

    # test environment variables
    env_vars = {
        "TRELLIS_PROVIDER": "ollama",
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_MODEL": "llama3",
        "OPENAI_API_KEY": "sk-test-key",
        "OPENAI_MODEL": "gpt-4o-mini",
        "ANTHROPIC_API_KEY": "sk-ant-test-key",
        "ANTHROPIC_MODEL": "claude-3-haiku",
    }

    with patch.dict(os.environ, env_vars, clear=True):
        yield
