from __future__ import annotations

import httpx
from ..settings import get_settings

from .base import BaseProvider
from . import register_provider

_SETTINGS = get_settings()


@register_provider("ollama")
class OllamaProvider(BaseProvider):
    """Ollama chat completion provider."""

    def _get_url(self) -> str:
        base = _SETTINGS.ollama_base_url
        if not base.startswith(("http://", "https://")):
            base = f"http://{base}"
        return f"{base}/v1/chat/completions"

    async def chat_complete(self, messages: list[dict], **kwargs: object) -> str:
        url = self._get_url()
        payload = {"model": _SETTINGS.ollama_model, "messages": messages}
        tools = kwargs.get("tools")
        if tools:
            payload["tools"] = tools
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
