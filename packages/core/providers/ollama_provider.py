from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from ..settings import get_settings

from .base import BaseProvider
from . import register_provider
from .exceptions import EmptyResponseError, InvalidResponseError

_SETTINGS = get_settings()


@register_provider("ollama")
class OllamaProvider(BaseProvider):
    """Ollama chat completion provider."""

    def _get_url(self) -> str:
        base = _SETTINGS.ollama_base_url
        if not base.startswith(("http://", "https://")):
            base = f"http://{base}"
        return f"{base}/v1/chat/completions"

    @retry(
        stop=stop_after_attempt(_SETTINGS.llm_max_retries),
        wait=wait_exponential(
            multiplier=1,
            min=_SETTINGS.llm_retry_min_wait,
            max=_SETTINGS.llm_retry_max_wait
        ),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True
    )
    async def chat_complete(self, messages: list[dict], **kwargs: object) -> str:
        url = self._get_url()
        payload = {"model": _SETTINGS.ollama_model, "messages": messages}
        tools = kwargs.get("tools")
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=_SETTINGS.llm_timeout_seconds) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            # validate response structure before accessing nested fields
            if "choices" not in data:
                raise InvalidResponseError("Ollama Response Missing 'choices' Field")

            if not data["choices"] or len(data["choices"]) == 0:
                raise EmptyResponseError("Ollama Response Has Empty Choices Array")

            choice = data["choices"][0]
            if "message" not in choice:
                raise InvalidResponseError("Ollama Choice Missing 'message' Field")

            if "content" not in choice["message"]:
                raise InvalidResponseError("Ollama Message Missing 'content' Field")

            content = choice["message"]["content"]
            if content is None:
                raise EmptyResponseError("Ollama Message Content Is None")

            return content
