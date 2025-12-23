from __future__ import annotations
import asyncio
import time
import logging
from enum import Enum
from typing import Any, Callable, Optional, TypeVar
from dataclasses import dataclass, field
from functools import wraps

from .providers.exceptions import ProviderError, ProviderRateLimitError, AgentTimeoutError

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5  # Failures before opening circuit
    success_threshold: int = 2  # Successes to close circuit from half-open
    timeout: float = 60.0  # Seconds before trying half-open
    half_open_max_calls: int = 1  # Max calls to allow in half-open state


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_state_change: float = field(default_factory=time.time)
    total_calls: int = 0
    total_failures: int = 0


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by stopping requests to failing services.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.stats = CircuitBreakerStats()
        self._lock = asyncio.Lock()

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function through circuit breaker."""
        async with self._lock:
            self.stats.total_calls += 1

            # Check circuit state
            if self.stats.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._set_half_open()
                else:
                    raise RuntimeError(
                        f"Circuit breaker {self.name} is OPEN. "
                        f"Service unavailable due to repeated failures."
                    )

            if self.stats.state == CircuitState.HALF_OPEN:
                if self.stats.success_count >= self.config.half_open_max_calls:
                    raise RuntimeError(
                        f"Circuit breaker {self.name} is HALF_OPEN. "
                        f"Maximum test calls reached."
                    )

        # Execute function
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            await self._record_success()
            return result

        except Exception as e:
            await self._record_failure(e)
            raise

    async def _record_success(self):
        """Record successful call."""
        async with self._lock:
            self.stats.failure_count = 0

            if self.stats.state == CircuitState.HALF_OPEN:
                self.stats.success_count += 1
                if self.stats.success_count >= self.config.success_threshold:
                    self._set_closed()
                    logger.info(f"Circuit breaker {self.name} closed after recovery")

    async def _record_failure(self, error: Exception):
        """Record failed call."""
        async with self._lock:
            self.stats.failure_count += 1
            self.stats.total_failures += 1
            self.stats.last_failure_time = time.time()

            if self.stats.state == CircuitState.HALF_OPEN:
                self._set_open()
                logger.warning(f"Circuit breaker {self.name} reopened after failed recovery attempt")

            elif self.stats.failure_count >= self.config.failure_threshold:
                self._set_open()
                logger.error(
                    f"Circuit breaker {self.name} opened after {self.stats.failure_count} failures. "
                    f"Last error: {error}"
                )

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.stats.last_failure_time is None:
            return False
        return (time.time() - self.stats.last_failure_time) >= self.config.timeout

    def _set_open(self):
        """Set circuit to OPEN state."""
        self.stats.state = CircuitState.OPEN
        self.stats.last_state_change = time.time()
        self.stats.success_count = 0

    def _set_half_open(self):
        """Set circuit to HALF_OPEN state."""
        self.stats.state = CircuitState.HALF_OPEN
        self.stats.last_state_change = time.time()
        self.stats.success_count = 0
        self.stats.failure_count = 0

    def _set_closed(self):
        """Set circuit to CLOSED state."""
        self.stats.state = CircuitState.CLOSED
        self.stats.last_state_change = time.time()
        self.stats.success_count = 0
        self.stats.failure_count = 0


# Global circuit breakers for providers
_circuit_breakers: dict[str, CircuitBreaker] = {}


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create circuit breaker for named service."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name)
    return _circuit_breakers[name]


async def with_timeout(coro, timeout_seconds: float, operation_name: str = "operation"):
    """
    Execute coroutine with timeout.

    Following 2025 best practice of per-node timeouts.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        logger.error(f"Timeout after {timeout_seconds}s for {operation_name}")
        raise AgentTimeoutError(
            f"{operation_name} timed out after {timeout_seconds} seconds"
        )


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    retry_on: tuple = (ProviderError,)
):
    """
    Decorator for retry logic with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff
        retry_on: Tuple of exception types to retry on

    Following 2025 best practices:
    - Exponential backoff for transient failures
    - Respect rate limit signals
    - Only retry retriable errors
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)

                except retry_on as e:
                    last_exception = e

                    # Don't retry non-retriable errors
                    if isinstance(e, ProviderError) and not e.retriable:
                        logger.warning(f"Non-retriable error, not retrying: {e}")
                        raise

                    # Respect rate limit retry-after header
                    if isinstance(e, ProviderRateLimitError) and e.retry_after:
                        delay = min(e.retry_after, max_delay)
                        logger.warning(f"Rate limited, waiting {delay}s before retry")
                        await asyncio.sleep(delay)
                        continue

                    # Don't retry on last attempt
                    if attempt == max_attempts - 1:
                        break

                    # Calculate exponential backoff delay
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    await asyncio.sleep(delay)

            # All attempts failed
            logger.error(f"All {max_attempts} attempts failed. Last error: {last_exception}")
            raise last_exception

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)

                except retry_on as e:
                    last_exception = e

                    if isinstance(e, ProviderError) and not e.retriable:
                        raise

                    if attempt == max_attempts - 1:
                        break

                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )

                    logger.warning(
                        f"Attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    time.sleep(delay)

            raise last_exception

        # Return appropriate wrapper
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
