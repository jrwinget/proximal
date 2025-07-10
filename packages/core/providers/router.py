from __future__ import annotations
from typing import List, Dict, Any
from ..settings import get_settings
from . import PROVIDER_REGISTRY

_settings = get_settings()
_provider_cache = {}


async def chat(messages: List[Dict[str, Any]], **kwargs: Any) -> str:
    """Route chat completion to the configured provider."""
    provider_name = _settings.provider_name.lower()
    
    if provider_name not in PROVIDER_REGISTRY:
        raise ValueError(f"Provider '{provider_name}' not found in registry")
    
    # Cache provider instances
    if provider_name not in _provider_cache:
        provider_cls = PROVIDER_REGISTRY[provider_name]
        _provider_cache[provider_name] = provider_cls()
    
    provider = _provider_cache[provider_name]
    return await provider.chat_complete(messages, **kwargs)