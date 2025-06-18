import httpx
from typing import List, Dict, Any
from ..settings import get_settings

_SETTINGS = get_settings()


class OllamaChat:
    """
    Minimal async wrapper that behaves like OpenAI ChatCompletion.create().
    """

    _url = f"{_SETTINGS.ollama_base_url}/v1/chat/completions"
    _model = _SETTINGS.ollama_model

    @classmethod
    async def acomplete(cls, messages: List[Dict[str, str]], tools=None) -> str:
        payload: Dict[str, Any] = {"model": cls._model, "messages": messages}
        if tools:
            payload["tools"] = tools
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(cls._url, json=payload)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
