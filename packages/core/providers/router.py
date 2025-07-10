from __future__ import annotations
from typing import Any
from importlib import metadata
from ..settings import get_settings
from packages.proximal.providers import (
    PROVIDER_REGISTRY,
    BaseProvider,
    register_provider,
    _load_plugins,
)

_provider_instance: BaseProvider | None = None


def _get_provider() -> BaseProvider:
    _load_plugins()
    global _provider_instance
    if _provider_instance is None:
        settings = get_settings()
        name = settings.provider_name.lower()
        cls = PROVIDER_REGISTRY.get(name)
        if not cls:
            raise ValueError(f"Unknown provider {name}")
        _provider_instance = cls()
    return _provider_instance


async def chat(messages: list[dict], tools: Any | None = None) -> str:
    provider = _get_provider()
    return await provider.chat_complete(messages, tools=tools)
