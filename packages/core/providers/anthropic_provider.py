from __future__ import annotations

from anthropic import AsyncAnthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..settings import get_settings

from .base import BaseProvider
from . import register_provider
from .exceptions import EmptyResponseError, InvalidResponseError

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

    @retry(
        stop=stop_after_attempt(_SETTINGS.llm_max_retries),
        wait=wait_exponential(
            multiplier=1,
            min=_SETTINGS.llm_retry_min_wait,
            max=_SETTINGS.llm_retry_max_wait
        ),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        reraise=True
    )
    async def chat_complete(self, messages: list[dict], **kwargs: object) -> str:
        tools = kwargs.get("tools")
        client = self._get_client()
        anthropic_messages = self._convert(messages)

        resp = await client.messages.create(
            model=_SETTINGS.anthropic_model,
            messages=anthropic_messages,
            max_tokens=4096,
            tools=tools,
            timeout=_SETTINGS.llm_timeout_seconds,
        )

        # validate response structure before accessing
        if not resp.content:
            raise EmptyResponseError("Anthropic Returned Empty Response - Check Model Configuration")

        if len(resp.content) == 0:
            raise EmptyResponseError("Anthropic Response Has No Content Blocks")

        # handle text content blocks (normal responses)
        first_block = resp.content[0]
        if hasattr(first_block, 'text'):
            return first_block.text

        # handle tool_use blocks when tools are provided
        if hasattr(first_block, 'type') and first_block.type == 'tool_use':
            raise InvalidResponseError(
                "Anthropic Returned Tool Use Block Instead Of Text - "
                "This Typically Means The Model Needs A Different Prompt"
            )

        raise InvalidResponseError(f"Anthropic Response Has Unexpected Content Type: {type(first_block)}")

    def _convert(self, messages: list[dict]) -> list[dict]:
        return messages
