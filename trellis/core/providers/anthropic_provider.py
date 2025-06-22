from anthropic import AsyncAnthropic
from ..settings import get_settings

_SETTINGS = get_settings()
_client = None


def get_client():
    """
    Lazy initialization of the Anthropic client.
    Only creates the client when actually needed.
    """
    global _client
    if _client is None:
        _client = AsyncAnthropic(
            api_key=_SETTINGS.anthropic_api_key,
            base_url=_SETTINGS.anthropic_base_url,
        )
    return _client


async def acomplete(messages, tools=None):
    """
    Async function to complete a conversation with Claude.

    Args:
        messages: List of message objects in the conversation
        tools: Optional list of tools for function calling

    Returns:
        The content of the model's response
    """
    client = get_client()

    anthropic_messages = _convert_to_anthropic_format(messages)

    kwargs = {
        "model": _SETTINGS.anthropic_model,
        "messages": anthropic_messages,
        "max_tokens": 4096,
    }

    if tools:
        kwargs["tools"] = tools

    response = await client.messages.create(**kwargs)

    return response.content[0].text


def _convert_to_anthropic_format(messages):
    """
    Convert messages from OpenAI format to Anthropic format if needed.

    Args:
        messages: List of message objects

    Returns:
        List of messages in Anthropic format
    """
    # anthropic's API expects messages in a specific format
    # this is a simple implementation that works for basic cases
    return messages
