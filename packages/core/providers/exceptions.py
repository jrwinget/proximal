"""exceptions for llm provider errors"""


class ProviderError(Exception):
    """base exception for provider-related errors"""
    pass


class EmptyResponseError(ProviderError):
    """raised when provider returns empty or no response"""
    pass


class InvalidResponseError(ProviderError):
    """raised when provider response doesn't match expected structure"""
    pass


class ProviderTimeoutError(ProviderError):
    """raised when provider request times out"""
    pass
