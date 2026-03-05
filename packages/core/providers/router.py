"""LLM chat completion via litellm."""

from __future__ import annotations

import logging
from typing import Any

import litellm

from ..settings import get_settings
from .exceptions import (
    EmptyResponseError,
    ProviderAuthenticationError,
    ProviderError,
    ProviderRateLimitError,
    ProviderServiceError,
    ProviderTimeoutError,
)

logger = logging.getLogger(__name__)

# lazy initialization flag for litellm config
_litellm_configured = False


def _configure_litellm() -> None:
    """Configure litellm retry settings on first use."""
    global _litellm_configured
    if _litellm_configured:
        return
    _litellm_configured = True
    settings = get_settings()
    litellm.num_retries = settings.llm_max_retries


async def chat(messages: list[dict[str, Any]], **kwargs: Any) -> str:
    """Route chat completion to the configured provider via litellm.

    Parameters
    ----------
    messages : list[dict[str, Any]]
        OpenAI-formatted chat messages.
    **kwargs : Any
        Extra arguments forwarded to ``litellm.acompletion`` (e.g. ``tools``,
        ``tool_choice``, ``temperature``).

    Returns
    -------
    str
        The assistant's text response.

    Raises
    ------
    ProviderAuthenticationError
        When the provider rejects the API key.
    ProviderRateLimitError
        When the provider rate-limits the request.
    ProviderTimeoutError
        When the request times out.
    ProviderServiceError
        When the provider returns a 5xx error.
    EmptyResponseError
        When the response contains no usable content.
    """
    _configure_litellm()
    settings = get_settings()
    model = settings.get_litellm_model()
    params = settings.get_litellm_params()

    try:
        response = await litellm.acompletion(
            model=model,
            messages=messages,
            **params,
            **kwargs,
        )
    except litellm.AuthenticationError as exc:
        raise ProviderAuthenticationError(
            f"Authentication failed: {exc}",
            provider=settings.provider_name,
        ) from exc
    except litellm.RateLimitError as exc:
        raise ProviderRateLimitError(
            f"Rate limit exceeded: {exc}",
            provider=settings.provider_name,
        ) from exc
    except litellm.Timeout as exc:
        raise ProviderTimeoutError(
            f"Request timed out: {exc}",
            provider=settings.provider_name,
        ) from exc
    except litellm.ServiceUnavailableError as exc:
        raise ProviderServiceError(
            f"Service unavailable: {exc}",
            provider=settings.provider_name,
        ) from exc
    except litellm.APIError as exc:
        raise ProviderError(
            f"API error: {exc}",
            retriable=True,
            provider=settings.provider_name,
        ) from exc

    # validate response
    if not response.choices:
        raise EmptyResponseError(
            "Provider returned empty choices",
            provider=settings.provider_name,
        )

    message = response.choices[0].message
    content = message.content

    if content is None:
        # return the raw response object when tool_calls are present
        # so structured_output can parse them
        if hasattr(message, "tool_calls") and message.tool_calls:
            return response

        raise EmptyResponseError(
            "Provider returned None content",
            provider=settings.provider_name,
        )

    return content
