from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseProvider(ABC):
    """Abstract interface for chat completion providers."""

    @abstractmethod
    async def chat_complete(self, messages: List[Dict[str, Any]], **kwargs: Any) -> str:
        """Return the assistant response for the given messages."""
        raise NotImplementedError
