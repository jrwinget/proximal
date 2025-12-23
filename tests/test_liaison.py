import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
import json
from datetime import datetime, timezone

from packages.core.agents.liaison import LiaisonAgent, MessageType, Tone, Audience
from packages.core.models import UserPreferences


# ============================================================================
# Fixtures and Test Data
# ============================================================================


@pytest.fixture
def liaison_agent():
    """Create a fresh LiaisonAgent instance for testing."""
    agent = LiaisonAgent()
    agent.reset_metrics()
    return agent


@pytest.fixture
def mock_user_preferences():
    """Mock user preferences with default values."""
    return UserPreferences(
        user_id="test_user",
        sprint_length_weeks=2,
        priority_system="P0-P3",
        tone="professional",
        work_hours_per_week=40,
        preferred_task_size="medium",
        include_breaks=True,
        timezone="UTC",
    )


@pytest.fixture
def sample_status_update_response():
    """Sample LLM response for status update message."""
    return json.dumps({
        "subject": "Status Update: Mobile App Development - Week 1",
        "message": (
            "Current Status: In Progress\n\n"
            "Completed This Week:\n"
            "- Set up React Native development environment\n"
            "- Created basic app scaffolding and navigation structure\n"
            "- Implemented user authentication flow\n\n"
            "Next Steps:\n"
            "- Design and implement home screen UI\n"
            "- Integrate backend API for data fetching\n"
            "- Begin user testing preparations\n\n"
            "Blockers: None at this time\n\n"
            "Timeline: On track for initial prototype by end of month."
        )
    })


@pytest.fixture
def sample_proposal_response():
    """Sample LLM response for project proposal."""
    return json.dumps({
        "subject": "Proposal: Modernize Customer Dashboard with Real-time Analytics",
        "message": (
            "Objective:\n"
            "Upgrade the customer dashboard to provide real-time analytics and improve user experience.\n\n"
            "Approach:\n"
            "1. Conduct user research to identify key metrics and pain points\n"
            "2. Design new dashboard layout with modern UI framework (React + D3.js)\n"
            "3. Implement WebSocket integration for real-time data updates\n"
            "4. Add customizable widget system for user preferences\n"
            "5. Comprehensive testing and gradual rollout\n\n"
            "Timeline Estimate: 8-10 weeks\n\n"
            "Resources Needed:\n"
            "- 2 frontend developers (full-time)\n"
            "- 1 backend developer (part-time for WebSocket implementation)\n"
            "- UX designer (2 weeks)\n\n"
            "Expected Outcomes:\n"
            "- 40% reduction in dashboard load time\n"
            "- Real-time data updates without page refresh\n"
            "- Increased user engagement and satisfaction\n"
            "- Reduced support tickets related to outdated data"
        )
    })


@pytest.fixture
def sample_help_request_response():
    """Sample LLM response for help request (neurodiverse-aware)."""
    return json.dumps({
        "subject": "Help Needed: Database Migration Performance Issues",
        "message": (
            "What I'm trying to achieve:\n"
            "Migrate 50M records from PostgreSQL to new schema while maintaining system availability.\n\n"
            "What I've tried:\n"
            "1. Basic batch migration (5000 records/batch) - took 12 hours for 1M records\n"
            "2. Increased batch size to 50k - caused database lock timeouts\n"
            "3. Tried parallel workers (4 workers) - conflicts with foreign key constraints\n\n"
            "Specific blocker:\n"
            "At current speed, migration would take 600+ hours (unacceptable downtime).\n"
            "Foreign key constraints prevent parallel processing.\n\n"
            "What would help:\n"
            "- Advice on optimal batch size balancing speed vs. locks\n"
            "- Strategies for handling FK constraints during migration\n"
            "- Code review of migration script (attached)\n"
            "- Alternatively: recommendation for proven migration tool\n\n"
            "Constraints:\n"
            "- Must complete during weekend maintenance window (48 hours max)\n"
            "- Cannot afford extended downtime\n"
            "- Limited to PostgreSQL 13 (no version upgrade option)"
        )
    })


# ============================================================================
# Message Type Tests
# ============================================================================


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_status_update_message_type(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences, sample_status_update_response
):
    """Test status update message generation with professional tone."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_status_update_response

    # Act
    result = await liaison_agent.draft_message(
        goal="Build mobile app for iOS and Android",
        message_type="status_update",
        tone="professional",
        audience="manager"
    )

    # Assert
    assert "subject" in result
    assert "message" in result
    assert len(result["message"]) > 50, "Message should have meaningful content"
    assert "Status Update" in result["subject"]
    assert "Mobile App" in result["subject"]

    # Verify LLM was called with correct structure
    mock_chat.assert_called_once()
    call_args = mock_chat.call_args
    messages = call_args[0][0]
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert "status update" in messages[0]["content"].lower()
    assert "manager" in messages[0]["content"]


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_proposal_message_type(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences, sample_proposal_response
):
    """Test project proposal generation with detailed structure."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_proposal_response

    # Act
    result = await liaison_agent.draft_message(
        goal="Modernize customer dashboard with real-time analytics",
        message_type="proposal",
        tone="professional",
        audience="manager",
        context={"approach": "Use React and WebSocket for real-time updates"}
    )

    # Assert
    assert "subject" in result
    assert "message" in result
    assert "Proposal" in result["subject"]
    assert len(result["message"]) > 100, "Proposal should be detailed"

    # Verify proposal structure elements
    message_lower = result["message"].lower()
    assert any(word in message_lower for word in ["objective", "goal", "purpose"])
    assert any(word in message_lower for word in ["approach", "method", "steps"])

    # Verify context was included in prompt
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "React and WebSocket" in call_args


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_progress_report_with_percentage(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test progress report with completion percentage."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    progress_response = json.dumps({
        "subject": "Progress Report: API Integration - 65% Complete",
        "message": (
            "Progress: 65% Complete\n\n"
            "Accomplishments:\n"
            "- Completed authentication endpoints (100%)\n"
            "- Implemented 8 of 12 resource endpoints (67%)\n"
            "- Added comprehensive error handling\n\n"
            "Remaining Work:\n"
            "- 4 remaining endpoints (estimated 1 week)\n"
            "- Integration testing (3 days)\n"
            "- Documentation updates (2 days)\n\n"
            "Timeline: On track for delivery next Friday"
        )
    })
    mock_chat.return_value = progress_response

    # Act
    result = await liaison_agent.draft_message(
        goal="Complete API integration for third-party service",
        message_type="progress",
        tone="professional",
        audience="manager",
        context={"progress_pct": 65}
    )

    # Assert
    assert "65%" in result["subject"] or "65" in result["message"]
    assert "progress" in result["subject"].lower()

    # Verify progress percentage in prompt
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "65%" in call_args or "progress_pct" in call_args.lower()


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_help_request_neurodiverse_aware(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences, sample_help_request_response
):
    """Test help request with neurodiverse-aware communication (clear, structured)."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_help_request_response

    # Act
    result = await liaison_agent.draft_message(
        goal="Database migration taking too long",
        message_type="help_request",
        tone="direct",
        audience="teammate",
        context={"blockers": "Migration would take 600+ hours at current speed"}
    )

    # Assert
    assert "help" in result["subject"].lower() or "need" in result["subject"].lower()
    assert len(result["message"]) > 100, "Help request should provide context"

    # Verify neurodiverse-aware prompt elements
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "clear" in call_args.lower()
    assert "specific" in call_args.lower()
    assert "neurodivergent" in call_args.lower() or "neurodiverse" in call_args.lower()


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_delegation_message_with_context(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test task delegation with assignee and deadline context."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    delegation_response = json.dumps({
        "subject": "Task Assignment: Implement User Settings Page",
        "message": (
            "Task: Implement User Settings Page\n\n"
            "Background:\n"
            "We're adding user profile customization to our app. Settings page needs to match design mockups.\n\n"
            "Success Criteria:\n"
            "- All fields from mockup are editable\n"
            "- Changes persist to database\n"
            "- Validation on all inputs\n"
            "- Mobile responsive design\n\n"
            "Timeline: Complete by Friday, Dec 30\n\n"
            "Resources:\n"
            "- Design mockups: [link]\n"
            "- API documentation: [link]\n"
            "- Similar implementation in Profile page (reference)\n\n"
            "Let me know if you need any clarification or run into blockers!"
        )
    })
    mock_chat.return_value = delegation_response

    # Act
    result = await liaison_agent.draft_message(
        goal="Implement user settings page",
        message_type="delegation",
        tone="casual",
        audience="teammate",
        context={
            "assignee": "Jordan",
            "deadline": "2024-12-30"
        }
    )

    # Assert
    assert "task" in result["subject"].lower() or "assignment" in result["subject"].lower()

    # Verify delegation context in prompt
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "Jordan" in call_args
    assert "2024-12-30" in call_args


# ============================================================================
# Tone Variation Tests
# ============================================================================


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_professional_tone(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test professional tone generates formal language."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = json.dumps({
        "subject": "Status Update: Project Alpha",
        "message": "I am pleased to report that Project Alpha is progressing according to schedule..."
    })

    # Act
    await liaison_agent.draft_message(
        goal="Project Alpha",
        message_type="status_update",
        tone="professional"
    )

    # Assert - verify prompt includes professional tone guidance
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "professional" in call_args.lower()
    assert "formal" in call_args.lower()


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_casual_tone(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test casual tone generates friendly, approachable language."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = json.dumps({
        "subject": "Quick Update: Project Alpha",
        "message": "Hey team! Just wanted to share a quick update on Project Alpha. Things are going great..."
    })

    # Act
    await liaison_agent.draft_message(
        goal="Project Alpha",
        message_type="status_update",
        tone="casual"
    )

    # Assert
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "casual" in call_args.lower()
    assert "friendly" in call_args.lower()


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_direct_tone(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test direct tone generates concise, to-the-point messages."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = json.dumps({
        "subject": "Project Alpha Status",
        "message": "Status: On track.\nCompleted: Auth module.\nNext: API integration.\nBlockers: None."
    })

    # Act
    await liaison_agent.draft_message(
        goal="Project Alpha",
        message_type="status_update",
        tone="direct"
    )

    # Assert
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "direct" in call_args.lower()
    assert "concise" in call_args.lower()


# ============================================================================
# Audience Adaptation Tests
# ============================================================================


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_manager_audience(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test manager audience focuses on outcomes and decisions."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = json.dumps({
        "subject": "Decision Required: Technology Stack Selection",
        "message": "Executive Summary: Need approval for React vs Angular..."
    })

    # Act
    await liaison_agent.draft_message(
        goal="Choose frontend framework",
        message_type="proposal",
        audience="manager"
    )

    # Assert
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "manager" in call_args.lower()
    assert "outcomes" in call_args.lower() or "decisions" in call_args.lower()


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_teammate_audience(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test teammate audience is collaborative with technical details."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = json.dumps({
        "subject": "Collaboration: API Integration Approach",
        "message": "Hey! Working on the API integration. Here's what I'm thinking..."
    })

    # Act
    await liaison_agent.draft_message(
        goal="API integration",
        message_type="delegation",
        audience="teammate"
    )

    # Assert
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "teammate" in call_args.lower()
    assert "collaborative" in call_args.lower()


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_client_audience(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test client audience focuses on value and next steps."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = json.dumps({
        "subject": "Project Milestone: Phase 1 Complete",
        "message": "We're excited to share that Phase 1 of your project is complete..."
    })

    # Act
    await liaison_agent.draft_message(
        goal="Client project update",
        message_type="progress",
        audience="client"
    )

    # Assert
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "client" in call_args.lower()
    assert "value" in call_args.lower() or "professional" in call_args.lower()


# ============================================================================
# Error Handling Tests
# ============================================================================


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_llm_json_parse_error(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test handling of invalid JSON response from LLM."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = "This is not valid JSON at all!"

    # Act & Assert
    with pytest.raises(ValueError, match="Failed to parse LLM response as JSON"):
        await liaison_agent.draft_message(
            goal="Test goal",
            message_type="status_update"
        )

    # Verify error was recorded in metrics
    assert liaison_agent.metrics["errors"] > 0


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_llm_missing_required_fields(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test handling of LLM response missing required fields."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = json.dumps({"only_subject": "Test"})  # Missing 'message' field

    # Act & Assert
    with pytest.raises(ValueError, match="missing required fields"):
        await liaison_agent.draft_message(
            goal="Test goal",
            message_type="status_update"
        )


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_message_too_short_validation(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test validation that message content is not too short."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = json.dumps({
        "subject": "Test",
        "message": "Too short"  # Less than 20 characters
    })

    # Act & Assert
    with pytest.raises(ValueError, match="too short"):
        await liaison_agent.draft_message(
            goal="Test goal",
            message_type="status_update"
        )


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_retry_on_llm_failure(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences, sample_status_update_response
):
    """Test retry logic when LLM fails initially but succeeds on retry."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences

    # First two calls fail, third succeeds
    mock_chat.side_effect = [
        Exception("Connection timeout"),
        Exception("Rate limit"),
        sample_status_update_response
    ]

    # Act
    result = await liaison_agent.draft_message(
        goal="Test goal",
        message_type="status_update"
    )

    # Assert
    assert result is not None
    assert "subject" in result
    assert mock_chat.call_count == 3  # Called 3 times due to retries
    assert liaison_agent.metrics["retries"] >= 2


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_retry_exhaustion(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test that retry gives up after max attempts."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.side_effect = Exception("Persistent failure")

    # Act & Assert
    with pytest.raises(Exception, match="Persistent failure"):
        await liaison_agent.draft_message(
            goal="Test goal",
            message_type="status_update"
        )

    # Verify retries were attempted (should be 3 total attempts)
    assert mock_chat.call_count == 3


# ============================================================================
# User Preferences Integration Tests
# ============================================================================


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_preferences_tone_override(
    mock_session_manager, mock_chat, liaison_agent, sample_status_update_response
):
    """Test that user preference tone overrides default when not explicitly set."""
    # Arrange
    casual_preferences = UserPreferences(
        tone="casual",  # User prefers casual tone
        work_hours_per_week=40
    )
    mock_session_manager.get_user_preferences.return_value = casual_preferences
    mock_chat.return_value = sample_status_update_response

    # Act - Don't explicitly set tone (defaults to professional)
    await liaison_agent.draft_message(
        goal="Test goal",
        message_type="status_update"
        # tone not specified, should use user preference
    )

    # Assert - Prompt should use casual tone from preferences
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "casual" in call_args.lower()


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_preferences_context_included(
    mock_session_manager, mock_chat, liaison_agent, sample_status_update_response
):
    """Test that user preferences context is included in prompts."""
    # Arrange
    preferences = UserPreferences(
        sprint_length_weeks=3,
        work_hours_per_week=30,
        preferred_task_size="small"
    )
    mock_session_manager.get_user_preferences.return_value = preferences
    mock_chat.return_value = sample_status_update_response

    # Act
    await liaison_agent.draft_message(
        goal="Test goal",
        message_type="status_update"
    )

    # Assert
    call_args = mock_chat.call_args[0][0][0]["content"]
    assert "30 hours/week" in call_args or "30" in call_args
    assert "small" in call_args


# ============================================================================
# Observability and Metrics Tests
# ============================================================================


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_metrics_recording(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences, sample_status_update_response
):
    """Test that metrics are properly recorded for each message."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_status_update_response
    liaison_agent.reset_metrics()

    # Act
    await liaison_agent.draft_message(
        goal="Test goal",
        message_type="status_update"
    )

    # Assert
    metrics = liaison_agent.get_metrics()
    assert metrics["messages_drafted"] == 1
    assert metrics["total_tokens"] > 0
    assert "status_update" in metrics["message_types"]
    assert metrics["message_types"]["status_update"] == 1


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_metrics_multiple_message_types(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test metrics tracking across different message types."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = json.dumps({
        "subject": "Test",
        "message": "This is a test message with enough content to pass validation checks."
    })

    # Act - Draft multiple different message types
    await liaison_agent.draft_message(goal="Goal 1", message_type="status_update")
    await liaison_agent.draft_message(goal="Goal 2", message_type="proposal")
    await liaison_agent.draft_message(goal="Goal 3", message_type="status_update")

    # Assert
    metrics = liaison_agent.get_metrics()
    assert metrics["messages_drafted"] == 3
    assert metrics["message_types"]["status_update"] == 2
    assert metrics["message_types"]["proposal"] == 1


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_token_estimation(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test that token usage is estimated reasonably."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences

    # Create a response with known word count
    # Subject: 5 words, Message: 20 words = 25 words total
    # Expected tokens: 25 * 1.3 = 32.5 ≈ 32
    mock_chat.return_value = json.dumps({
        "subject": "This is a test subject",  # 5 words
        "message": "This is a longer test message with exactly twenty words to verify token estimation calculations are working correctly overall."  # 20 words
    })
    liaison_agent.reset_metrics()

    # Act
    await liaison_agent.draft_message(goal="Test", message_type="status_update")

    # Assert
    metrics = liaison_agent.get_metrics()
    # 25 words * 1.3 = 32.5, rounds to 32
    assert metrics["total_tokens"] >= 30  # Approximately correct
    assert metrics["total_tokens"] <= 35


def test_metrics_reset(liaison_agent):
    """Test that metrics can be reset."""
    # Arrange
    liaison_agent.metrics["messages_drafted"] = 10
    liaison_agent.metrics["errors"] = 5

    # Act
    liaison_agent.reset_metrics()

    # Assert
    assert liaison_agent.metrics["messages_drafted"] == 0
    assert liaison_agent.metrics["errors"] == 0
    assert liaison_agent.metrics["message_types"] == {}


# ============================================================================
# Performance and Timeout Tests
# ============================================================================


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_timeout_parameter_passed(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences, sample_status_update_response
):
    """Test that timeout parameter is passed to LLM call."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_status_update_response

    # Act
    await liaison_agent.draft_message(
        goal="Test",
        message_type="status_update",
        timeout=60  # Custom timeout
    )

    # Assert
    call_kwargs = mock_chat.call_args[1]
    assert "timeout" in call_kwargs
    assert call_kwargs["timeout"] == 60


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_default_timeout(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences, sample_status_update_response
):
    """Test default timeout is 30 seconds."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_status_update_response

    # Act
    await liaison_agent.draft_message(
        goal="Test",
        message_type="status_update"
    )

    # Assert
    call_kwargs = mock_chat.call_args[1]
    assert call_kwargs["timeout"] == 30


# ============================================================================
# Memory Integration Tests
# ============================================================================


@pytest.mark.asyncio
@patch("packages.core.agents.liaison.mem")
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_memory_persistence(
    mock_session_manager, mock_chat, mock_mem, liaison_agent, mock_user_preferences, sample_status_update_response
):
    """Test that drafted messages are persisted to memory."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_status_update_response
    mock_batch = MagicMock()
    mock_mem.batch = mock_batch

    # Act
    result = await liaison_agent.draft_message(
        goal="Build mobile app",
        message_type="status_update"
    )

    # Assert
    mock_batch.add_data_object.assert_called_once()
    call_args = mock_batch.add_data_object.call_args[0]
    data_object = call_args[0]

    assert data_object["role"] == "liaison"
    assert data_object["goal"] == "Build mobile app"
    assert data_object["message_type"] == "status_update"
    assert data_object["subject"] == result["subject"]
    assert data_object["message"] == result["message"]
    assert "timestamp" in data_object


@pytest.mark.asyncio
@patch("packages.core.agents.liaison.mem")
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_memory_persistence_failure_doesnt_break(
    mock_session_manager, mock_chat, mock_mem, liaison_agent, mock_user_preferences, sample_status_update_response
):
    """Test that memory persistence failure doesn't break message drafting."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_status_update_response
    mock_batch = MagicMock()
    mock_batch.add_data_object.side_effect = Exception("Memory service down")
    mock_mem.batch = mock_batch

    # Act - Should not raise exception
    result = await liaison_agent.draft_message(
        goal="Test",
        message_type="status_update"
    )

    # Assert - Message still generated successfully
    assert result is not None
    assert "subject" in result
    assert "message" in result


# ============================================================================
# Output Quality Validation Tests
# ============================================================================


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_subject_line_relevance(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test that subject lines are relevant to the goal."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = json.dumps({
        "subject": "Mobile App Development Status Update",
        "message": "Current progress on the mobile app development project..."
    })

    # Act
    result = await liaison_agent.draft_message(
        goal="Build mobile app for customer tracking",
        message_type="status_update"
    )

    # Assert - Subject should relate to the goal
    subject_lower = result["subject"].lower()
    assert any(keyword in subject_lower for keyword in ["mobile", "app", "status"])


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_message_clarity_structure(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test that messages have clear structure with paragraphs or bullets."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = json.dumps({
        "subject": "Test Subject",
        "message": (
            "Introduction paragraph explaining the context.\n\n"
            "Key points:\n"
            "- First important point\n"
            "- Second important point\n\n"
            "Conclusion with next steps."
        )
    })

    # Act
    result = await liaison_agent.draft_message(
        goal="Test",
        message_type="status_update"
    )

    # Assert - Should have structure (multiple paragraphs or bullets)
    message = result["message"]
    has_paragraphs = "\n\n" in message
    has_bullets = any(char in message for char in ["-", "•", "*"])
    assert has_paragraphs or has_bullets, "Message should have clear structure"


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_message_appropriate_length_for_type(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Test that message length is appropriate for message type."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences

    # Proposal should be longer than status update
    proposal_response = json.dumps({
        "subject": "Proposal",
        "message": "This is a comprehensive project proposal with multiple sections covering objectives, approach, timeline, resources, and expected outcomes. " * 10
    })

    status_response = json.dumps({
        "subject": "Status",
        "message": "Brief status update with current progress and next steps outlined clearly."
    })

    # Act
    mock_chat.return_value = proposal_response
    proposal_result = await liaison_agent.draft_message(
        goal="Test",
        message_type="proposal"
    )

    mock_chat.return_value = status_response
    status_result = await liaison_agent.draft_message(
        goal="Test",
        message_type="status_update"
    )

    # Assert - Proposal should generally be longer
    # Note: In production, LLM would ensure this; we're testing the expectation
    assert len(proposal_result["message"]) > 100, "Proposal should be detailed"
    assert len(status_result["message"]) > 20, "Status should have content"


# ============================================================================
# Integration Scenario Tests
# ============================================================================


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_complete_help_request_scenario(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences, sample_help_request_response
):
    """Integration test: Complete help request scenario when stuck on a problem."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_help_request_response

    # Act - Developer stuck on database migration
    result = await liaison_agent.draft_message(
        goal="Migrate 50M database records without downtime",
        message_type="help_request",
        tone="direct",
        audience="teammate",
        context={
            "blockers": "Current approach would take 600+ hours, need to complete in 48-hour window"
        }
    )

    # Assert - Comprehensive validation
    assert "help" in result["subject"].lower() or "need" in result["subject"].lower()
    assert len(result["message"]) > 100, "Help request should provide detailed context"

    # Verify neurodiverse-aware elements in prompt
    prompt = mock_chat.call_args[0][0][0]["content"]
    assert "clear" in prompt.lower()
    assert "specific" in prompt.lower()
    assert "blockers" in prompt

    # Verify metrics tracked
    assert liaison_agent.metrics["messages_drafted"] == 1
    assert liaison_agent.metrics["message_types"]["help_request"] == 1


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_complete_delegation_scenario(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences
):
    """Integration test: Delegating task with full context."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    delegation_response = json.dumps({
        "subject": "New Task: API Documentation Update",
        "message": (
            "Hi Alex,\n\n"
            "I'm assigning you the API documentation update task.\n\n"
            "Context: We've added 5 new endpoints to our REST API and customers "
            "are asking for updated docs.\n\n"
            "What needs to be done:\n"
            "- Document 5 new endpoints with examples\n"
            "- Update authentication section\n"
            "- Add code samples in Python and JavaScript\n\n"
            "Success looks like:\n"
            "- All endpoints documented in OpenAPI format\n"
            "- Working code examples tested\n"
            "- Peer review from Sarah\n\n"
            "Timeline: Please complete by end of next week (Jan 31)\n\n"
            "Resources:\n"
            "- Endpoint specs in JIRA-1234\n"
            "- Current docs in /docs/api\n"
            "- Example format in /docs/templates\n\n"
            "Let me know if you have questions!"
        )
    })
    mock_chat.return_value = delegation_response

    # Act
    result = await liaison_agent.draft_message(
        goal="Update API documentation for new endpoints",
        message_type="delegation",
        tone="casual",
        audience="teammate",
        context={
            "assignee": "Alex",
            "deadline": "2025-01-31",
        }
    )

    # Assert
    assert "task" in result["subject"].lower() or "assignment" in result["subject"].lower()
    message_lower = result["message"].lower()

    # Should include delegation essentials
    assert any(word in message_lower for word in ["context", "background", "needs"])
    assert "alex" in message_lower
    assert "jan 31" in message_lower or "2025-01-31" in result["message"]


# ============================================================================
# Backward Compatibility Tests
# ============================================================================


def test_legacy_sync_method(liaison_agent):
    """Test backward compatibility with synchronous draft_message method."""
    # Act
    result = liaison_agent.draft_message_sync("Build mobile app")

    # Assert
    assert isinstance(result, str)
    assert "Build mobile app" in result


# ============================================================================
# Edge Cases and Boundary Tests
# ============================================================================


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_empty_context(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences, sample_status_update_response
):
    """Test handling of empty context dictionary."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_status_update_response

    # Act - Should not raise error
    result = await liaison_agent.draft_message(
        goal="Test",
        message_type="status_update",
        context={}
    )

    # Assert
    assert result is not None


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_none_context(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences, sample_status_update_response
):
    """Test handling of None context (default parameter)."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_status_update_response

    # Act
    result = await liaison_agent.draft_message(
        goal="Test",
        message_type="status_update",
        context=None
    )

    # Assert
    assert result is not None


@pytest.mark.asyncio
@patch("packages.core.providers.router.chat")
@patch("packages.core.agents.liaison.session_manager")
async def test_long_goal_text(
    mock_session_manager, mock_chat, liaison_agent, mock_user_preferences, sample_status_update_response
):
    """Test handling of very long goal text."""
    # Arrange
    mock_session_manager.get_user_preferences.return_value = mock_user_preferences
    mock_chat.return_value = sample_status_update_response

    long_goal = "Build a comprehensive mobile application " * 50  # Very long goal

    # Act
    result = await liaison_agent.draft_message(
        goal=long_goal,
        message_type="status_update"
    )

    # Assert - Should handle gracefully
    assert result is not None
    prompt = mock_chat.call_args[0][0][0]["content"]
    assert long_goal in prompt
