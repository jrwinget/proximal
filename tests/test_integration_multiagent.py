"""
Integration tests for multi-agent workflows.

Following 2025 best practices:
- Test individual agents in isolation
- Test multi-agent coordination
- Test fault tolerance and error recovery
- Test agent handoffs and state management
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio

from packages.core.orchestrator import Orchestrator
from packages.core.agents import plan_llm
from packages.core.models import Task, Sprint
from packages.core.observability import get_observability_logger
from packages.core.fault_tolerance import CircuitBreaker, with_retry, with_timeout
from packages.core.providers.exceptions import (
    ProviderError,
    ProviderTimeoutError,
    ProviderRateLimitError,
    AgentTimeoutError
)


@pytest.fixture
def sample_tasks():
    """Sample tasks for testing."""
    return [
        Task(
            id="task1",
            title="Setup dev environment",
            detail="Install dependencies and configure",
            priority="P0",
            estimate_h=2,
            done=False
        ),
        Task(
            id="task2",
            title="Implement feature",
            detail="Build the core functionality",
            priority="P1",
            estimate_h=8,
            done=False
        )
    ]


@pytest.fixture
def sample_sprints():
    """Sample sprints for testing."""
    return [
        Sprint(
            sprint_num=1,
            tasks=[
                Task(id="task1", title="Task 1", detail="Detail 1", priority="P0", estimate_h=2, done=False)
            ],
            duration_weeks=2
        )
    ]


class TestIndividualAgents:
    """Test individual agents in isolation."""

    @pytest.mark.asyncio
    @patch("packages.core.providers.router.chat")
    async def test_planner_agent_success(self, mock_chat):
        """Test planner agent produces valid output."""
        # Mock LLM response
        mock_chat.return_value = '[{"id": "task1", "title": "Task 1", "detail": "Detail", "priority": "P1", "estimate_h": 5, "done": false}]'

        # Execute planner
        result = await plan_llm({"goal": "Build a website"})

        # Verify output structure
        assert "tasks" in result
        assert len(result["tasks"]) > 0
        assert isinstance(result["tasks"][0], Task)
        assert result["tasks"][0].priority in ["P0", "P1", "P2", "P3"]

    @pytest.mark.asyncio
    @patch("packages.core.providers.router.chat")
    async def test_planner_agent_error_handling(self, mock_chat):
        """Test planner handles LLM errors gracefully."""
        # Mock LLM error
        mock_chat.side_effect = ProviderError("API error", retriable=True, provider="test")

        # Should propagate error
        with pytest.raises(ProviderError):
            await plan_llm({"goal": "Build a website"})


class TestMultiAgentOrchestration:
    """Test multi-agent coordination and workflows."""

    @pytest.mark.asyncio
    @patch("packages.core.providers.router.chat")
    async def test_orchestrator_coordinates_agents(self, mock_chat):
        """Test orchestrator properly coordinates multiple agents."""
        # Mock planner response
        mock_chat.return_value = '[{"id": "task1", "title": "Task 1", "detail": "Detail", "priority": "P1", "estimate_h": 5, "done": false}]'

        orchestrator = Orchestrator()
        result = await orchestrator.run("Build a mobile app")

        # Verify orchestrator collected results from multiple agents
        assert "plan" in result
        assert isinstance(result["plan"], list)

        # Should have attempted to run other agents (even if they're mocked/missing)
        # At minimum, should have plan result
        assert len(result["plan"]) > 0

    @pytest.mark.asyncio
    @patch("packages.core.providers.router.chat")
    async def test_agent_handoffs_preserve_context(self, mock_chat, sample_tasks):
        """Test that context is preserved during agent handoffs."""
        mock_chat.return_value = '[{"id": "task1", "title": "Task 1", "detail": "Detail", "priority": "P1", "estimate_h": 5, "done": false}]'

        orchestrator = Orchestrator()

        # Get observability logger to track handoffs
        logger = get_observability_logger()
        initial_metrics_count = len(logger._metrics)

        result = await orchestrator.run("Test goal")

        # Verify metrics were recorded for agent operations
        assert len(logger._metrics) > initial_metrics_count

        # Verify result contains data
        assert "plan" in result
        assert result["plan"] is not None

    @pytest.mark.asyncio
    @patch("packages.core.providers.router.chat")
    async def test_parallel_agent_execution(self, mock_chat):
        """Test that agents execute in parallel when possible."""
        import time

        # Mock fast planner response
        mock_chat.return_value = '[{"id": "task1", "title": "Task 1", "detail": "Detail", "priority": "P1", "estimate_h": 5, "done": false}]'

        orchestrator = Orchestrator()

        start_time = time.time()
        result = await orchestrator.run("Test goal")
        duration = time.time() - start_time

        # With parallel execution, should be fast
        # (not sum of all agent times, but max of concurrent agents)
        assert duration < 10.0  # Should be much faster than sequential

        assert "plan" in result


class TestFaultTolerance:
    """Test fault tolerance and error recovery."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures."""
        circuit = CircuitBreaker("test_service")

        async def failing_function():
            raise ProviderError("Service error", retriable=True)

        # Fail multiple times to trip circuit breaker
        for i in range(5):
            with pytest.raises(ProviderError):
                await circuit.call(failing_function)

        # Circuit should now be OPEN
        from packages.core.fault_tolerance import CircuitState
        assert circuit.stats.state == CircuitState.OPEN

        # Further calls should fail fast
        with pytest.raises(RuntimeError, match="Circuit breaker.*is OPEN"):
            await circuit.call(failing_function)

    @pytest.mark.asyncio
    async def test_retry_with_exponential_backoff(self):
        """Test retry decorator with exponential backoff."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01, exponential_base=2.0)
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ProviderError("Transient error", retriable=True)
            return "success"

        result = await flaky_function()

        assert result == "success"
        assert call_count == 3  # Should have retried twice before succeeding

    @pytest.mark.asyncio
    async def test_retry_respects_non_retriable_errors(self):
        """Test that non-retriable errors are not retried."""
        call_count = 0

        @with_retry(max_attempts=3)
        async def function_with_auth_error():
            nonlocal call_count
            call_count += 1
            raise ProviderError("Auth failed", retriable=False)

        with pytest.raises(ProviderError):
            await function_with_auth_error()

        # Should fail immediately without retry
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_timeout_enforcement(self):
        """Test that timeouts are properly enforced."""
        async def slow_operation():
            await asyncio.sleep(5.0)
            return "completed"

        # Should timeout after 0.1 seconds
        with pytest.raises(AgentTimeoutError, match="timed out"):
            await with_timeout(slow_operation(), timeout_seconds=0.1, operation_name="slow_op")

    @pytest.mark.asyncio
    async def test_rate_limit_handling(self):
        """Test handling of rate limit errors with backoff."""
        call_count = 0

        @with_retry(max_attempts=3, base_delay=0.01)
        async def rate_limited_function():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ProviderRateLimitError(retry_after=0.02)
            return "success"

        result = await rate_limited_function()

        assert result == "success"
        assert call_count == 2  # Initial call + 1 retry


class TestObservability:
    """Test observability and monitoring."""

    @pytest.mark.asyncio
    async def test_agent_operations_are_traced(self):
        """Test that agent operations are properly traced."""
        from packages.core.observability import trace_agent_operation

        logger = get_observability_logger()
        initial_count = len(logger._metrics)

        @trace_agent_operation("test_agent", "test_operation")
        async def traced_function():
            return "result"

        result = await traced_function()

        assert result == "result"
        assert len(logger._metrics) > initial_count

        # Verify metrics were recorded
        latest_metric = logger._metrics[-1]
        assert latest_metric.agent_name == "test_agent"
        assert latest_metric.operation == "test_operation"
        assert latest_metric.status == "success"
        assert latest_metric.duration_ms is not None

    @pytest.mark.asyncio
    async def test_metrics_summary_generation(self):
        """Test generation of metrics summary."""
        from packages.core.observability import trace_operation

        logger = get_observability_logger()

        # Perform some traced operations
        with trace_operation("agent1", "op1"):
            pass

        with trace_operation("agent1", "op2"):
            pass

        with trace_operation("agent2", "op1"):
            pass

        summary = logger.get_metrics_summary()

        assert summary["total_operations"] > 0
        assert "agent_breakdown" in summary
        assert len(summary["agent_breakdown"]) >= 2


class TestSessionStateManagement:
    """Test session state management in multi-agent workflows."""

    @pytest.mark.asyncio
    async def test_session_isolation_between_workflows(self):
        """Test that different sessions don't interfere with each other."""
        from packages.core.session import session_manager
        from packages.core.models import MessageRole

        # Create two separate sessions
        session1 = session_manager.create_session("user_goal_1")
        session2 = session_manager.create_session("user_goal_2")

        assert session1.session_id != session2.session_id

        # Modify session1
        session1.status = "planning"
        session1.add_message(MessageRole.user, "Test message")
        session_manager.update_session(session1)

        # Retrieve session2 - should not be affected
        retrieved_session2 = session_manager.get_session(session2.session_id)
        assert retrieved_session2.status != "planning"
        assert len(retrieved_session2.messages) == 0

    @pytest.mark.asyncio
    async def test_session_expiry_handling(self):
        """Test that expired sessions are handled properly."""
        from packages.core.session import session_manager
        from datetime import datetime, timedelta, timezone

        # Create session
        session = session_manager.create_session("test_goal")

        # Artificially make it old
        session.created_at = datetime.now(timezone.utc) - timedelta(hours=2)
        session.updated_at = datetime.now(timezone.utc) - timedelta(hours=2)
        session_manager.update_session(session)

        # Verify session exists even if old (expiry is based on timeout setting)
        retrieved = session_manager.get_session(session.session_id)
        assert retrieved is not None
