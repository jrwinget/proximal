"""Capability registry — typed functions that can be tools, agent interfaces, or standalone."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass
class Capability:
    """A registered capability with metadata.

    Attributes
    ----------
    name : str
        Unique identifier for the capability.
    description : str
        Human-readable description of what the capability does.
    fn : Callable
        The callable implementing the capability.
    requires_llm : bool
        Whether this capability needs an LLM provider to function.
    category : str
        Logical grouping (e.g. ``"planning"``, ``"wellness"``).
    """

    name: str
    description: str
    fn: Callable
    requires_llm: bool = False
    category: str = "planning"


CAPABILITY_REGISTRY: dict[str, Capability] = {}


def register_capability(
    name: str,
    description: str,
    category: str = "planning",
    requires_llm: bool = False,
) -> Callable:
    """Decorator to register a capability.

    Parameters
    ----------
    name : str
        Unique name for this capability.
    description : str
        What the capability does.
    category : str, optional
        Logical grouping, by default ``"planning"``.
    requires_llm : bool, optional
        Whether an LLM call is needed, by default ``False``.

    Returns
    -------
    Callable
        The original function, unmodified.
    """

    def decorator(fn: Callable) -> Callable:
        CAPABILITY_REGISTRY[name] = Capability(
            name=name,
            description=description,
            fn=fn,
            requires_llm=requires_llm,
            category=category,
        )
        return fn

    return decorator
