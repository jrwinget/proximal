"""Capability registry — typed functions that can be tools, agent interfaces, or standalone."""

from .registry import Capability, CAPABILITY_REGISTRY, register_capability

# import capability modules to trigger registration
from . import productivity  # noqa: F401
from . import wellness  # noqa: F401
from . import communication  # noqa: F401
from . import planning  # noqa: F401
from . import voice  # noqa: F401

__all__ = [
    "Capability",
    "CAPABILITY_REGISTRY",
    "register_capability",
]
