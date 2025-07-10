from __future__ import annotations
from typing import Callable, Dict, Type
from importlib import metadata

AGENT_REGISTRY: Dict[str, Type] = {}


def register_agent(name: str):
    """Decorator to register an agent class by name."""

    def decorator(cls):
        AGENT_REGISTRY[name] = cls
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