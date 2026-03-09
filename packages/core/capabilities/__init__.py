"""Capability registry — typed functions that can be tools, agent interfaces, or standalone."""

# import capability modules to trigger registration
from . import (
    communication,  # noqa: F401
    planning,  # noqa: F401
    productivity,  # noqa: F401
    voice,  # noqa: F401
    wellness,  # noqa: F401
)
from .registry import CAPABILITY_REGISTRY, Capability, register_capability

__all__ = [
    "Capability",
    "CAPABILITY_REGISTRY",
    "register_capability",
]
