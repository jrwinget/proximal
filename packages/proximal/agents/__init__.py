from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable, Dict, Type

AGENT_REGISTRY: Dict[str, Type["BaseAgent"]] = {}


def register_agent(name: str) -> Callable[[Type["BaseAgent"]], Type["BaseAgent"]]:
    """Decorator to register an agent class by name."""

    def decorator(cls: Type["BaseAgent"]) -> Type["BaseAgent"]:
        AGENT_REGISTRY[name] = cls
        return cls

    return decorator


class BaseAgent(ABC):
    """Base class for all agents."""

    @abstractmethod
    def __init__(self) -> None:
        """Initialize the agent."""

    @abstractmethod
    def __repr__(self) -> str:  # pragma: no cover - simple representation
        return f"{self.__class__.__name__}()"
