"""LLM provider abstraction via litellm."""

from .exceptions import (
    AgentError,
    AgentTimeoutError,
    ProviderError,
)
from .exceptions import (
    ProviderAuthenticationError as AuthenticationError,
)
from .exceptions import (
    ProviderRateLimitError as RateLimitError,
)
from .router import chat

__all__ = [
    "chat",
    "ProviderError",
    "RateLimitError",
    "AuthenticationError",
    "AgentError",
    "AgentTimeoutError",
]
