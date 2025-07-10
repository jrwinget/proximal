from __future__ import annotations

from openai import AsyncOpenAI
from ..settings import get_settings

from .base import BaseProvider
from . import register_provider

_SETTINGS = get_settings()


@register_provider("openai")
class OpenAIProvider(BaseProvider):
    """OpenAI chat completion provider."""

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=_SETTINGS.openai_api_key,
                base_url=_SETTINGS.openai_base_url,
            )
        return self._client

    async def chat_complete(self, messages: list[dict], **kwargs: object) -> str:
        tools = kwargs.get("tools")
        client = self._get_client()
        resp = await client.chat.completions.create(
            model=_SETTINGS.openai_model,
            messages=messages,
            tools=tools,
        )
        return resp.choices[0].message.content
