from __future__ import annotations

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..settings import get_settings

from .base import BaseProvider
from . import register_provider
from .exceptions import EmptyResponseError, InvalidResponseError

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
                timeout=_SETTINGS.llm_timeout_seconds,
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

        resp = await client.chat.completions.create(
            model=_SETTINGS.openai_model,
            messages=messages,
            tools=tools,
        )

        # validate response structure before accessing
        if not resp.choices:
            raise EmptyResponseError("OpenAI Returned Empty Choices - Check Model Configuration")

        if len(resp.choices) == 0:
            raise EmptyResponseError("OpenAI Response Has No Choices")

        message = resp.choices[0].message

        # content can be None for tool calls or refusals
        if message.content is None:
            # check if this is a tool call response
            if hasattr(message, 'tool_calls') and message.tool_calls:
                raise InvalidResponseError(
                    "OpenAI Returned Tool Call Instead Of Text - "
                    "This Typically Means The Model Needs A Different Prompt"
                )
            # check for refusal
            if hasattr(message, 'refusal') and message.refusal:
                raise InvalidResponseError(f"OpenAI Refused To Answer: {message.refusal}")

            raise EmptyResponseError("OpenAI Message Content Is None - Unknown Reason")

        return message.content
