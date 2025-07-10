from __future__ import annotations

from importlib import metadata
from typing import Callable, Dict, Type

from .base import BaseProvider

PROVIDER_REGISTRY: Dict[str, Type[BaseProvider]] = {}


def register_provider(name: str) -> Callable[[Type[BaseProvider]], Type[BaseProvider]]:
    def decorator(cls: Type[BaseProvider]) -> Type[BaseProvider]:
        PROVIDER_REGISTRY[name] = cls
        return cls

    return decorator


_loaded_plugins = False


def _load_plugins() -> None:
    global _loaded_plugins
    if _loaded_plugins:
        return
    _loaded_plugins = True
    for ep in metadata.entry_points(group="proximal.plugins"):
        try:
            ep.load()
        except Exception:
            pass


_load_plugins()

from .openai_provider import OpenAIProvider  # noqa: F401,E402
from .ollama_provider import OllamaProvider  # noqa: F401,E402
from .anthropic_provider import AnthropicProvider  # noqa: F401,E402
