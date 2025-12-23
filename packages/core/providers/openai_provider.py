from __future__ import annotations
import time
import logging
from openai import AsyncOpenAI, APIError, APITimeoutError, RateLimitError, AuthenticationError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..settings import get_settings
from ..observability import get_observability_logger
from ..fault_tolerance import get_circuit_breaker

from .base import BaseProvider
from . import register_provider
from .exceptions import (
    EmptyResponseError,
    InvalidResponseError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    ProviderAuthenticationError,
    ProviderServiceError
)

_SETTINGS = get_settings()
logger = logging.getLogger(__name__)


@register_provider("openai")
class OpenAIProvider(BaseProvider):

    def __init__(self) -> None:
        self._client: AsyncOpenAI | None = None
        self.obs_logger = get_observability_logger()
        self.circuit_breaker = get_circuit_breaker("openai_provider")

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
        retry=retry_if_exception_type((ConnectionError, TimeoutError, APITimeoutError)),
        reraise=True
    )
    async def chat_complete(self, messages: list[dict], **kwargs: object) -> str:
        """
        Execute chat completion with OpenAI.

        Implements:
        - Circuit breaker pattern
        - Token usage tracking
        - Comprehensive error handling
        - LLM call observability
        """
        tools = kwargs.get("tools")
        client = self._get_client()
        start_time = time.time()

        try:
            # Execute through circuit breaker
            async def _make_api_call():
                return await client.chat.completions.create(
                    model=_SETTINGS.openai_model,
                    messages=messages,
                    tools=tools,
                )

            resp = await self.circuit_breaker.call(_make_api_call)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Extract token usage
            prompt_tokens = resp.usage.prompt_tokens if resp.usage else None
            completion_tokens = resp.usage.completion_tokens if resp.usage else None

            # Log LLM call with metrics
            self.obs_logger.log_llm_call(
                provider="openai",
                model=_SETTINGS.openai_model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                duration_ms=duration_ms
            )

            # Validate response structure
            if not resp.choices or len(resp.choices) == 0:
                raise EmptyResponseError(
                    "OpenAI Returned Empty Choices - Check Model Configuration",
                    provider="openai"
                )

            message = resp.choices[0].message

            # Handle None content
            if message.content is None:
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    raise InvalidResponseError(
                        "OpenAI Returned Tool Call Instead Of Text",
                        provider="openai"
                    )
                if hasattr(message, 'refusal') and message.refusal:
                    raise InvalidResponseError(
                        f"OpenAI Refused To Answer: {message.refusal}",
                        provider="openai"
                    )
                raise EmptyResponseError(
                    "OpenAI Message Content Is None",
                    provider="openai"
                )

            logger.info(
                f"OpenAI call successful: {prompt_tokens or 0} prompt tokens, "
                f"{completion_tokens or 0} completion tokens, {duration_ms:.2f}ms"
            )

            return message.content

        except AuthenticationError as e:
            logger.error(f"OpenAI authentication failed: {e}")
            self.obs_logger.log_llm_call(
                provider="openai",
                model=_SETTINGS.openai_model,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
            raise ProviderAuthenticationError(
                f"OpenAI authentication failed: {e}",
                provider="openai"
            )

        except RateLimitError as e:
            logger.warning(f"OpenAI rate limit hit: {e}")
            self.obs_logger.log_llm_call(
                provider="openai",
                model=_SETTINGS.openai_model,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
            raise ProviderRateLimitError(
                f"OpenAI rate limit exceeded: {e}",
                provider="openai"
            )

        except APITimeoutError as e:
            logger.error(f"OpenAI request timed out: {e}")
            self.obs_logger.log_llm_call(
                provider="openai",
                model=_SETTINGS.openai_model,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
            raise ProviderTimeoutError(
                f"OpenAI request timed out: {e}",
                provider="openai"
            )

        except APIError as e:
            logger.error(f"OpenAI API error: {e}")
            self.obs_logger.log_llm_call(
                provider="openai",
                model=_SETTINGS.openai_model,
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
            # 5xx errors are retriable
            if hasattr(e, 'status_code') and 500 <= e.status_code < 600:
                raise ProviderServiceError(
                    f"OpenAI service error: {e}",
                    provider="openai"
                )
            # Other API errors are not retriable
            raise InvalidResponseError(
                f"OpenAI API error: {e}",
                provider="openai"
            )
