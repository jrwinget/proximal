import httpx
from typing import Any
from ..settings import get_settings

_SETTINGS = get_settings()


class OllamaChat:
    _model = _SETTINGS.ollama_model

    @classmethod
    def _get_url(cls) -> str:
        base = _SETTINGS.ollama_base_url
        if not base.startswith(("http://", "https://")):
            base = f"http://{base}"
        return f"{base}/v1/chat/completions"

    @classmethod
    async def acomplete(cls, messages: list[dict], tools: Any = None) -> str:
        url = cls._get_url()
        payload = {"model": cls._model, "messages": messages}
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
