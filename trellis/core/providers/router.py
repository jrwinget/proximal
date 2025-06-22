from ..settings import get_settings
from .ollama_provider import OllamaChat
from .openai_provider import acomplete as openai_acomplete
from .anthropic_provider import acomplete as anthropic_acomplete

_SETTINGS = get_settings()


async def chat(messages, tools=None) -> str:
    """
    Route the chat request to the appropriate provider.

    Args:
        messages: List of message objects in the conversation
        tools: Optional list of tools for function calling

    Returns:
        The content of the model's response
    """
    prov = _SETTINGS.trellis_provider.lower()

    if prov == "ollama":
        return await OllamaChat.acomplete(messages, tools)

    if prov == "openai":
        return await openai_acomplete(messages, tools)

    if prov == "anthropic":
        return await anthropic_acomplete(messages, tools)

    raise ValueError(f"Unknown provider {prov}")
