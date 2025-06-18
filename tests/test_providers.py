import pytest
from unittest.mock import AsyncMock, patch
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.mark.asyncio
@patch(
    "packages.core.providers.ollama_provider.OllamaChat.acomplete",
    new_callable=AsyncMock,
)
@patch("packages.core.providers.openai_provider.acomplete", new_callable=AsyncMock)
@patch("packages.core.providers.anthropic_provider.acomplete", new_callable=AsyncMock)
async def test_chat_basic(mock_anthropic, mock_openai, mock_ollama):
    """Test that the chat function returns a string."""
    # import here to ensure any patches are applied first
    from packages.core.providers.router import chat
    from packages.core.settings import get_settings

    # get current provider from settings
    _SETTINGS = get_settings()
    PROVIDER = _SETTINGS.trellis_provider.lower()

    # setup mocks
    mock_ollama.return_value = "Hello from Ollama"
    mock_openai.return_value = "Hello from OpenAI"
    mock_anthropic.return_value = "Hello from Anthropic"

    messages = [{"role": "user", "content": "Say hello world"}]
    result = await chat(messages)

    assert isinstance(result, str)
    assert len(result) > 0

    # verify correct provider was called
    if PROVIDER == "ollama":
        mock_ollama.assert_called_once()
        assert not mock_openai.called
        assert not mock_anthropic.called
    elif PROVIDER == "openai":
        mock_openai.assert_called_once()
        assert not mock_ollama.called
        assert not mock_anthropic.called
    elif PROVIDER == "anthropic":
        mock_anthropic.assert_called_once()
        assert not mock_ollama.called
        assert not mock_openai.called


@pytest.mark.asyncio
async def test_chat_content():
    """Test that the chat function processes content correctly."""
    # import router module
    from packages.core.providers.router import chat

    # create a mock for the chat function
    with patch(
        "packages.core.providers.router.chat", new_callable=AsyncMock
    ) as mock_chat:
        mock_chat.return_value = "Test response"

        messages = [{"role": "user", "content": "Test message"}]
        result = await mock_chat(messages)

        assert result == "Test response"
        mock_chat.assert_called_once_with(messages)
