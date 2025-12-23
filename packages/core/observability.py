"""
Observability and tracing infrastructure for multi-agent systems.

Following 2025 best practices:
- Full production tracing for all agent operations
- Structured logging with context
- Performance metrics tracking
- Agent-level monitoring
"""
from __future__ import annotations
import logging
import time
import functools
from typing import Any, Callable, Dict, Optional
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class AgentMetrics:
    """Metrics for individual agent operations."""

    agent_name: str
    operation: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    duration_ms: Optional[float] = None
    status: str = "running"  # running, success, error
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def complete(self, status: str = "success", error: Optional[str] = None):
        """Mark operation as complete and calculate duration."""
        self.end_time = time.time()
        self.duration_ms = (self.end_time - self.start_time) * 1000
        self.status = status
        self.error = error

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for logging."""
        return {
            "agent_name": self.agent_name,
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            "status": self.status,
            "error": self.error,
            "timestamp": datetime.fromtimestamp(self.start_time).isoformat(),
            **self.metadata
        }


class ObservabilityLogger:
    """Centralized observability logger with structured logging."""

    def __init__(self, name: str = "proximal"):
        self.logger = logging.getLogger(name)
        self._metrics: list[AgentMetrics] = []

    def log_agent_start(self, agent_name: str, operation: str, **metadata) -> AgentMetrics:
        """Log start of agent operation."""
        metrics = AgentMetrics(agent_name=agent_name, operation=operation, metadata=metadata)
        self._metrics.append(metrics)

        self.logger.info(
            f"Agent operation started: {agent_name}.{operation}",
            extra={
                "agent_name": agent_name,
                "operation": operation,
                "event": "agent_start",
                **metadata
            }
        )
        return metrics

    def log_agent_complete(
        self,
        metrics: AgentMetrics,
        status: str = "success",
        error: Optional[str] = None,
        **additional_metadata
    ):
        """Log completion of agent operation."""
        metrics.complete(status=status, error=error)
        metrics.metadata.update(additional_metadata)

        log_func = self.logger.info if status == "success" else self.logger.error
        log_func(
            f"Agent operation completed: {metrics.agent_name}.{metrics.operation} ({metrics.duration_ms:.2f}ms)",
            extra={
                "event": "agent_complete",
                **metrics.to_dict()
            }
        )

    def log_agent_handoff(self, from_agent: str, to_agent: str, context: Dict[str, Any]):
        """Log agent handoff for tracing multi-agent workflows."""
        self.logger.info(
            f"Agent handoff: {from_agent} -> {to_agent}",
            extra={
                "event": "agent_handoff",
                "from_agent": from_agent,
                "to_agent": to_agent,
                "context_keys": list(context.keys()),
                "timestamp": datetime.now().isoformat()
            }
        )

    def log_llm_call(
        self,
        provider: str,
        model: str,
        prompt_tokens: Optional[int] = None,
        completion_tokens: Optional[int] = None,
        duration_ms: Optional[float] = None,
        error: Optional[str] = None
    ):
        """Log LLM API call with token usage."""
        self.logger.info(
            f"LLM call: {provider}/{model}",
            extra={
                "event": "llm_call",
                "provider": provider,
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": (prompt_tokens or 0) + (completion_tokens or 0),
                "duration_ms": duration_ms,
                "error": error,
                "timestamp": datetime.now().isoformat()
            }
        )

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get summary of all collected metrics."""
        if not self._metrics:
            return {"total_operations": 0}

        completed = [m for m in self._metrics if m.duration_ms is not None]

        return {
            "total_operations": len(self._metrics),
            "completed_operations": len(completed),
            "successful_operations": len([m for m in completed if m.status == "success"]),
            "failed_operations": len([m for m in completed if m.status == "error"]),
            "average_duration_ms": sum(m.duration_ms for m in completed) / len(completed) if completed else 0,
            "agent_breakdown": self._get_agent_breakdown()
        }

    def _get_agent_breakdown(self) -> Dict[str, Dict[str, Any]]:
        """Get per-agent metrics breakdown."""
        breakdown = {}
        for metrics in self._metrics:
            if metrics.agent_name not in breakdown:
                breakdown[metrics.agent_name] = {
                    "total_calls": 0,
                    "successful_calls": 0,
                    "failed_calls": 0,
                    "total_duration_ms": 0
                }

            breakdown[metrics.agent_name]["total_calls"] += 1
            if metrics.status == "success":
                breakdown[metrics.agent_name]["successful_calls"] += 1
            elif metrics.status == "error":
                breakdown[metrics.agent_name]["failed_calls"] += 1
            if metrics.duration_ms:
                breakdown[metrics.agent_name]["total_duration_ms"] += metrics.duration_ms

        return breakdown


# Global observability logger instance
_global_logger: Optional[ObservabilityLogger] = None


def get_observability_logger() -> ObservabilityLogger:
    """Get the global observability logger instance."""
    global _global_logger
    if _global_logger is None:
        _global_logger = ObservabilityLogger()
    return _global_logger


def trace_agent_operation(agent_name: str, operation: str):
    """
    Decorator to automatically trace agent operations.

    Usage:
        @trace_agent_operation("planner", "plan_llm")
        async def plan_llm(state: dict) -> dict:
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_observability_logger()
            metrics = logger.log_agent_start(agent_name, operation)

            try:
                result = await func(*args, **kwargs)
                logger.log_agent_complete(metrics, status="success")
                return result
            except Exception as e:
                logger.log_agent_complete(metrics, status="error", error=str(e))
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_observability_logger()
            metrics = logger.log_agent_start(agent_name, operation)

            try:
                result = func(*args, **kwargs)
                logger.log_agent_complete(metrics, status="success")
                return result
            except Exception as e:
                logger.log_agent_complete(metrics, status="error", error=str(e))
                raise

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


@contextmanager
def trace_operation(agent_name: str, operation: str, **metadata):
    """
    Context manager for tracing operations.

    Usage:
        with trace_operation("orchestrator", "coordinate_agents"):
            # operation code
            pass
    """
    logger = get_observability_logger()
    metrics = logger.log_agent_start(agent_name, operation, **metadata)

    try:
        yield metrics
        logger.log_agent_complete(metrics, status="success")
    except Exception as e:
        logger.log_agent_complete(metrics, status="error", error=str(e))
        raise
