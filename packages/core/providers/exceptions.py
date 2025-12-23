from typing import Optional


class ProviderError(Exception):
    """Base exception for provider-related errors."""

    def __init__(self, message: str, retriable: bool = False, provider: Optional[str] = None):
        super().__init__(message)
        self.retriable = retriable
        self.provider = provider


class EmptyResponseError(ProviderError):
    """Raised when provider returns empty or no response."""

    def __init__(self, message: str = "Provider returned empty response", provider: Optional[str] = None):
        super().__init__(message, retriable=True, provider=provider)


class InvalidResponseError(ProviderError):
    """Raised when provider response doesn't match expected structure."""

    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(message, retriable=False, provider=provider)


class ProviderTimeoutError(ProviderError):
    """Raised when provider request times out."""

    def __init__(self, message: str = "Provider request timed out", provider: Optional[str] = None):
        super().__init__(message, retriable=True, provider=provider)


class ProviderRateLimitError(ProviderError):
    """Raised when provider rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Provider rate limit exceeded",
        retry_after: Optional[int] = None,
        provider: Optional[str] = None
    ):
        super().__init__(message, retriable=True, provider=provider)
        self.retry_after = retry_after


class ProviderAuthenticationError(ProviderError):
    """Raised when provider authentication fails."""

    def __init__(self, message: str = "Provider authentication failed", provider: Optional[str] = None):
        super().__init__(message, retriable=False, provider=provider)


class ProviderServiceError(ProviderError):
    """Raised when provider service is unavailable (5xx errors)."""

    def __init__(self, message: str = "Provider service error", provider: Optional[str] = None):
        super().__init__(message, retriable=True, provider=provider)


# Agent-specific exceptions
class AgentError(Exception):
    """Base exception for agent-related errors."""

    def __init__(self, message: str, agent_name: Optional[str] = None):
        super().__init__(message)
        self.agent_name = agent_name


class AgentTimeoutError(AgentError):
    """Raised when agent operation times out."""

    pass


class AgentValidationError(AgentError):
    """Raised when agent input/output validation fails."""

    pass
