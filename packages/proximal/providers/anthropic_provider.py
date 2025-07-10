from __future__ import annotations

from anthropic import AsyncAnthropic
from packages.core.settings import get_settings

from .base import BaseProvider
from packages.proximal.providers import register_provider

_SETTINGS = get_settings()


@register_provider("anthropic")
class AnthropicProvider(BaseProvider):
    """Anthropic Claude chat completion provider."""

    def __init__(self) -> None:
        self._client: AsyncAnthropic | None = None

    def _get_client(self) -> AsyncAnthropic:
        if self._client is None:
            self._client = AsyncAnthropic(
                api_key=_SETTINGS.anthropic_api_key,
                base_url=_SETTINGS.anthropic_base_url,
            )
        return self._client

    async def chat_complete(self, messages: list[dict], **kwargs: object) -> str:
        tools = kwargs.get("tools")
        client = self._get_client()
        anthropic_messages = self._convert(messages)
        resp = await client.messages.create(
            model=_SETTINGS.anthropic_model,
            messages=anthropic_messages,
            max_tokens=4096,
            tools=tools,
        )
        return resp.content[0].text

    def _convert(self, messages: list[dict]) -> list[dict]:
        return messages
