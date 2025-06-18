from openai import AsyncOpenAI
from ..settings import get_settings

_SETTINGS = get_settings()
_client = None


def get_client():
    """
    Lazy initialization of the OpenAI client.
    Only creates the client when actually needed.
    """
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            api_key=_SETTINGS.openai_api_key,
            base_url=_SETTINGS.openai_base_url,
        )
    return _client


async def acomplete(messages, tools=None):
    """
    Async function to complete a conversation with OpenAI.

    Args:
        messages: List of message objects in the conversation
        tools: Optional list of tools for function calling

    Returns:
        The content of the model's response
    """
    client = get_client()
    resp = await client.chat.completions.create(
        model=_SETTINGS.openai_model,
        messages=messages,
        tools=tools,
    )
    return resp.choices[0].message.content
