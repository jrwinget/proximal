import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


@pytest.fixture
def mock_litellm_response():
    """Create a mock litellm response object."""
    mock_choice = MagicMock()
    mock_choice.message.content = "test response"
    mock_choice.message.tool_calls = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage.prompt_tokens = 10
    mock_response.usage.completion_tokens = 20
    return mock_response


@pytest.fixture
def empty_choices_response():
    """Create a mock litellm response with no choices."""
    mock_response = MagicMock()
    mock_response.choices = []
    return mock_response


@pytest.fixture
def none_content_response():
    """Create a mock litellm response with None content."""
    mock_choice = MagicMock()
    mock_choice.message.content = None
    mock_choice.message.tool_calls = None

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


@pytest.mark.asyncio
async def test_chat_returns_string(mock_litellm_response):
    """chat() should return the string content from litellm response."""
    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        return_value=mock_litellm_response,
    ):
        from packages.core.providers.router import chat

        result = await chat([{"role": "user", "content": "hello"}])
        assert result == "test response"
        assert isinstance(result, str)


@pytest.mark.asyncio
async def test_chat_passes_messages_to_litellm(mock_litellm_response):
    """chat() should pass messages through to litellm.acompletion."""
    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        return_value=mock_litellm_response,
    ) as mock_completion:
        from packages.core.providers.router import chat

        messages = [{"role": "user", "content": "test"}]
        await chat(messages)
        call_kwargs = mock_completion.call_args
        assert call_kwargs.kwargs["messages"] == messages


@pytest.mark.asyncio
async def test_chat_passes_kwargs_to_litellm(mock_litellm_response):
    """chat() should forward extra kwargs like tools and tool_choice."""
    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        return_value=mock_litellm_response,
    ) as mock_completion:
        from packages.core.providers.router import chat

        tools = [{"type": "function", "function": {"name": "test"}}]
        await chat([{"role": "user", "content": "hi"}], tools=tools, tool_choice="auto")
        call_kwargs = mock_completion.call_args.kwargs
        assert call_kwargs["tools"] == tools
        assert call_kwargs["tool_choice"] == "auto"


@pytest.mark.asyncio
async def test_chat_empty_choices_raises(empty_choices_response):
    """chat() should raise ProviderError when response has no choices."""
    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        return_value=empty_choices_response,
    ):
        from packages.core.providers.exceptions import ProviderError
        from packages.core.providers.router import chat

        with pytest.raises(ProviderError, match="empty"):
            await chat([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_chat_none_content_raises(none_content_response):
    """chat() should raise ProviderError when message content is None."""
    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        return_value=none_content_response,
    ):
        from packages.core.providers.exceptions import ProviderError
        from packages.core.providers.router import chat

        with pytest.raises(ProviderError, match="[Ee]mpty|[Nn]one"):
            await chat([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_chat_authentication_error():
    """chat() should wrap litellm AuthenticationError into ProviderAuthenticationError."""
    import litellm

    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=litellm.AuthenticationError(
            message="bad key", llm_provider="openai", model="gpt-4o-mini"
        ),
    ):
        from packages.core.providers.exceptions import ProviderAuthenticationError
        from packages.core.providers.router import chat

        with pytest.raises(ProviderAuthenticationError):
            await chat([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_chat_rate_limit_error():
    """chat() should wrap litellm RateLimitError into ProviderRateLimitError."""
    import litellm

    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=litellm.RateLimitError(
            message="rate limited", llm_provider="openai", model="gpt-4o-mini"
        ),
    ):
        from packages.core.providers.exceptions import ProviderRateLimitError
        from packages.core.providers.router import chat

        with pytest.raises(ProviderRateLimitError):
            await chat([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_chat_timeout_error():
    """chat() should wrap litellm Timeout into ProviderTimeoutError."""
    import litellm

    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=litellm.Timeout(
            message="timeout", llm_provider="openai", model="gpt-4o-mini"
        ),
    ):
        from packages.core.providers.exceptions import ProviderTimeoutError
        from packages.core.providers.router import chat

        with pytest.raises(ProviderTimeoutError):
            await chat([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_chat_service_error():
    """chat() should wrap litellm ServiceUnavailableError into ProviderServiceError."""
    import litellm

    with patch(
        "litellm.acompletion",
        new_callable=AsyncMock,
        side_effect=litellm.ServiceUnavailableError(
            message="service down", llm_provider="openai", model="gpt-4o-mini"
        ),
    ):
        from packages.core.providers.exceptions import ProviderServiceError
        from packages.core.providers.router import chat

        with pytest.raises(ProviderServiceError):
            await chat([{"role": "user", "content": "hi"}])


@pytest.mark.asyncio
async def test_chat_content_returned(mock_litellm_response):
    """Chat function can be patched directly for downstream tests."""
    with patch(
        "packages.core.providers.router.chat", new_callable=AsyncMock
    ) as mock_chat:
        mock_chat.return_value = "Test"
        result = await mock_chat([{"role": "user", "content": "hi"}])
        assert result == "Test"
        mock_chat.assert_called_once()


def test_provider_imports():
    """Public API should expose chat and exception classes."""
    from packages.core.providers import (
        AuthenticationError,
        ProviderError,
        RateLimitError,
        chat,
    )

    assert callable(chat)
    assert issubclass(RateLimitError, ProviderError)
    assert issubclass(AuthenticationError, ProviderError)


def test_settings_get_litellm_model():
    """Settings should provide a litellm model string."""
    with patch.dict(
        os.environ,
        {
            "PROVIDER_NAME": "openai",
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_MODEL": "gpt-4o-mini",
            "SKIP_WEAVIATE_CONNECTION": "1",
        },
        clear=True,
    ):
        from packages.core.settings import Settings

        s = Settings()
        model_str = s.get_litellm_model()
        assert model_str == "gpt-4o-mini"


def test_settings_get_litellm_model_ollama():
    """Settings should prefix ollama models with 'ollama/'."""
    with patch.dict(
        os.environ,
        {
            "PROVIDER_NAME": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "llama3",
            "SKIP_WEAVIATE_CONNECTION": "1",
        },
        clear=True,
    ):
        from packages.core.settings import Settings

        s = Settings()
        model_str = s.get_litellm_model()
        assert model_str == "ollama/llama3"


def test_settings_get_litellm_model_anthropic():
    """Settings should prefix anthropic models with 'anthropic/'."""
    with patch.dict(
        os.environ,
        {
            "PROVIDER_NAME": "anthropic",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "ANTHROPIC_MODEL": "claude-3-haiku",
            "SKIP_WEAVIATE_CONNECTION": "1",
        },
        clear=True,
    ):
        from packages.core.settings import Settings

        s = Settings()
        model_str = s.get_litellm_model()
        assert model_str == "anthropic/claude-3-haiku"


def test_settings_get_litellm_params_ollama():
    """Settings should include api_base for ollama provider."""
    with patch.dict(
        os.environ,
        {
            "PROVIDER_NAME": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "llama3",
            "SKIP_WEAVIATE_CONNECTION": "1",
        },
        clear=True,
    ):
        from packages.core.settings import Settings

        s = Settings()
        params = s.get_litellm_params()
        assert params["api_base"] == "http://localhost:11434"


def test_settings_get_litellm_params_openai():
    """Settings should include api_key for openai provider."""
    with patch.dict(
        os.environ,
        {
            "PROVIDER_NAME": "openai",
            "OPENAI_API_KEY": "sk-test",
            "OPENAI_MODEL": "gpt-4o-mini",
            "SKIP_WEAVIATE_CONNECTION": "1",
        },
        clear=True,
    ):
        from packages.core.settings import Settings

        s = Settings()
        params = s.get_litellm_params()
        assert params["api_key"] == "sk-test"


def test_settings_get_litellm_params_anthropic():
    """Settings should include api_key for anthropic provider."""
    with patch.dict(
        os.environ,
        {
            "PROVIDER_NAME": "anthropic",
            "ANTHROPIC_API_KEY": "sk-ant-test",
            "ANTHROPIC_MODEL": "claude-3-haiku",
            "SKIP_WEAVIATE_CONNECTION": "1",
        },
        clear=True,
    ):
        from packages.core.settings import Settings

        s = Settings()
        params = s.get_litellm_params()
        assert params["api_key"] == "sk-ant-test"
