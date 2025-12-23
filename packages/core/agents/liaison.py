from __future__ import annotations
from typing import Dict, Any, Optional, Literal, List
import json
from datetime import datetime, timezone
from enum import StrEnum

from . import PlannerAgent
from .registry import register_agent
from ..providers.router import chat as chat_model
from ..providers.exceptions import (
    ProviderError,
    EmptyResponseError,
    AgentValidationError,
)
from ..session import session_manager
from ..memory import client as mem
from ..observability import trace_agent_operation, get_observability_logger
from ..fault_tolerance import with_retry, with_timeout
from ..settings import get_settings


class MessageType(StrEnum):
    """Supported message types for communication drafting."""

    status_update = "status_update"
    proposal = "proposal"
    progress = "progress"
    help_request = "help_request"
    delegation = "delegation"


class Tone(StrEnum):
    """Communication tone options."""

    professional = "professional"
    casual = "casual"
    direct = "direct"


class Audience(StrEnum):
    """Target audience types."""

    manager = "manager"
    teammate = "teammate"
    client = "client"
    public = "public"


# Few-shot examples for advanced prompt engineering
# These examples teach the LLM the expected quality and style
FEW_SHOT_EXAMPLES = {
    "status_update": {
        "professional": {
            "input": "Build authentication system, 60% complete, need AWS credentials",
            "output": {
                "subject": "Authentication System Progress - Credentials Needed",
                "message": """I'm making solid progress on the authentication system implementation.

Current Status:
- JWT token generation and validation: Complete
- User registration and login flows: Complete
- Password reset functionality: In progress (60% complete)

Next Steps:
- Complete password reset feature
- Add email verification
- Comprehensive integration testing

Blocker:
I need AWS SES credentials to implement the email functionality. Could you provide access or point me to the right person?

Timeline: On track for Friday delivery assuming credentials by EOD tomorrow.""",
            },
        },
        "casual": {
            "input": "Fixed the API bug, working on tests now",
            "output": {
                "subject": "Fixed that API bug!",
                "message": """Hey! Quick win today - got that API performance issue sorted out.

What I did:
- Found the N+1 query problem in the user endpoint
- Added eager loading for related data
- Response time dropped from 3s to 200ms

Now working on:
- Adding regression tests so this doesn't come back
- Documenting the fix for the team

Should have it all wrapped up by end of day. Let me know if you want a quick demo!""",
            },
        },
    },
    "help_request": {
        "direct": {
            "input": "Stuck on memory leak, tried profiling, energy low",
            "output": {
                "subject": "Help: Memory Leak in Worker Process",
                "message": """I'm stuck on a memory leak and could use another pair of eyes.

Problem: Worker processes growing to 2GB+ over 24 hours, then crashing

What I've tried:
- Profiling with memory_profiler - inconclusive
- Reviewed recent code changes - nothing obvious
- Checked for circular references - found none

Current theory: Might be related to the background task queue

Ask: Could you pair with me tomorrow AM (when I'll have more energy) to debug? 30-60 min should be enough.

Impact: Production workers restarting every 6 hours, affecting job reliability.""",
            },
        },
    },
    "delegation": {
        "professional": {
            "input": "Review PR #342, caching layer, medium complexity",
            "output": {
                "subject": "PR Review Request: Caching Layer Implementation",
                "message": """I'd value your review on PR #342 when you have bandwidth.

What it is:
- New Redis caching layer for API responses
- About 250 LOC across 3 files
- Includes comprehensive unit tests

Why your review:
Your experience with our Redis setup makes you perfect for this. I especially want feedback on the cache invalidation strategy.

Timeline:
No rush - targeting merge by end of week. Happy to pair review if that works better for you.

Link: https://github.com/org/repo/pull/342""",
            },
        },
    },
}

# Template-based fallback for graceful degradation when LLM fails
FALLBACK_TEMPLATES = {
    "status_update": {
        "professional": """Subject: Update: {goal}

Status update on {goal}.

Current status: {status}
Completed: {completed}
In progress: {in_progress}
Blockers: {blockers}

Next steps: {next_steps}

Timeline: {timeline}""",
        "casual": """Subject: Quick update on {goal}

Hey! Quick update on {goal}.

Done: {completed}
Working on: {in_progress}
Stuck on: {blockers}

Next up: {next_steps}""",
        "direct": """Subject: {goal} Status

Status: {status}
Done: {completed}
Current: {in_progress}
Blockers: {blockers}
Next: {next_steps}""",
    },
}


@register_agent("liaison")
class LiaisonAgent(PlannerAgent):
    """
    Production-grade LLM-powered communication assistant.

    Advanced Features:
    ----------------
    1. Prompt Engineering:
       - Few-shot learning with curated examples
       - Chain-of-thought prompting for complex messages
       - Context-aware template selection
       - Audience and tone adaptation

    2. Fault Tolerance:
       - Automatic retry with exponential backoff
       - Timeout protection for LLM calls
       - Graceful degradation to templates on failure
       - Comprehensive error handling

    3. Observability:
       - Structured logging with trace IDs
       - Performance metrics tracking
       - Token usage monitoring for cost awareness
       - Success/failure rate tracking

    4. User Experience:
       - Neurodiverse-friendly communication patterns
       - Energy and capacity awareness
       - Anti-anxiety framing
       - Clear, actionable language

    5. Production Readiness:
       - Input validation with helpful error messages
       - Response validation and sanitization
       - Memory persistence for learning
       - Backward compatibility

    Example Usage:
    -------------
    Basic status update:
        >>> agent = LiaisonAgent()
        >>> result = await agent.draft_message(
        ...     goal="Build authentication system",
        ...     message_type="status_update",
        ...     audience="manager"
        ... )
        >>> print(result["message"])
        >>> print(f"Tokens used: {result['estimated_tokens']}")

    Help request with low energy:
        >>> result = await agent.draft_message(
        ...     goal="Debug production memory leak",
        ...     message_type="help_request",
        ...     audience="teammate",
        ...     tone="direct",
        ...     context={
        ...         "issue": "Worker memory growing unbounded",
        ...         "tried": ["Profiling", "Code review", "Documentation"],
        ...         "energy": "low",
        ...         "impact": "Workers crashing every 6 hours"
        ...     }
        ... )

    Progress report with metrics:
        >>> result = await agent.draft_message(
        ...     goal="Q4 API Development",
        ...     message_type="progress",
        ...     audience="client",
        ...     context={
        ...         "completed": ["Auth API", "User management", "Payment integration"],
        ...         "in_progress": "Reporting dashboard",
        ...         "progress_pct": 75,
        ...         "timeline": "On track for Nov 30"
        ...     }
        ... )

    Advanced delegation:
        >>> result = await agent.draft_message(
        ...     goal="Review caching implementation PR",
        ...     message_type="delegation",
        ...     audience="teammate",
        ...     context={
        ...         "pr_number": "342",
        ...         "complexity": "medium",
        ...         "files_changed": 8,
        ...         "why_you": "Redis expertise",
        ...         "specific_asks": ["Cache invalidation strategy", "Error handling"]
        ...     }
        ... )
    """

    def __init__(self) -> None:
        super().__init__()
        self.settings = get_settings()
        self.logger = get_observability_logger()
        self.metrics: Dict[str, Any] = {
            "messages_drafted": 0,
            "total_tokens": 0,
            "errors": 0,
            "retries": 0,
            "llm_failures": 0,
            "template_fallbacks": 0,
            "message_types": {},
            "audience_breakdown": {},
            "tone_breakdown": {},
        }

    def __repr__(self) -> str:
        return "LiaisonAgent()"

    @trace_agent_operation("liaison", "draft_message")
    @with_retry(
        max_attempts=3,
        base_delay=1.0,
        max_delay=10.0,
        retry_on=(ProviderError,),
    )
    async def draft_message(
        self,
        goal: str,
        message_type: Literal[
            "status_update", "proposal", "progress", "help_request", "delegation"
        ] = "status_update",
        audience: Literal["manager", "teammate", "client", "public"] = "teammate",
        tone: Optional[Literal["professional", "casual", "direct"]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Draft a context-aware communication message using advanced LLM prompting.

        Args:
            goal: The main topic, project, or task being communicated about.
                  Should be concise but descriptive (e.g., "Build authentication system")

            message_type: Type of communication message:
                - "status_update": Regular progress update on ongoing work
                - "proposal": Proposing a new approach, feature, or decision
                - "progress": Detailed progress report with metrics and timeline
                - "help_request": Requesting assistance or unblocking
                - "delegation": Delegating work or requesting action from others

            audience: Target audience for the message:
                - "manager": Manager or supervisor (focus on decisions, outcomes, timeline)
                - "teammate": Peer team member (collaborative, detailed, contextual)
                - "client": External client/stakeholder (professional, value-focused)
                - "public": Public communication (accessible, clear, professional)

            tone: Communication tone (uses user preference if not specified):
                - "professional": Formal, structured, comprehensive
                - "casual": Friendly, conversational, approachable
                - "direct": Concise, to-the-point, minimal pleasantries
                - None: Use user's default preference from settings

            context: Additional context dictionary with optional keys:
                Core context:
                - "progress_pct": Completion percentage (0-100)
                - "status": Current status description
                - "completed": List or description of completed items
                - "in_progress": Current work items
                - "blockers": List or description of blocking issues
                - "next_steps": Planned next actions

                Help request context:
                - "issue": Specific problem or challenge
                - "tried": What solutions have been attempted
                - "impact": Business/technical impact
                - "energy": Current energy level ("high"/"medium"/"low")
                - "capacity": Available capacity for new work

                Delegation context:
                - "assignee": Who should do this (optional)
                - "deadline": Target deadline
                - "why_you": Why this person is suited for the task
                - "specific_asks": Specific questions or areas to focus on

                Timeline context:
                - "timeline": Timeline status or estimate
                - "risks": Identified risks or concerns

        Returns:
            Dictionary with:
                - "subject": Email subject line (None if not applicable)
                - "message": The drafted message body
                - "tone": Tone that was used (resolved from preference if not specified)
                - "estimated_tokens": Approximate token count for cost tracking
                - "metadata": Additional metadata (generation_method, timestamp, etc.)

        Raises:
            AgentValidationError: If input validation fails (invalid parameters)
            ProviderError: If LLM provider fails after all retry attempts

        Examples:
            Simple status update:
            >>> result = await agent.draft_message(
            ...     goal="Implement user dashboard",
            ...     message_type="status_update",
            ...     audience="manager"
            ... )

            Help request with context:
            >>> result = await agent.draft_message(
            ...     goal="Optimize database queries",
            ...     message_type="help_request",
            ...     audience="teammate",
            ...     context={
            ...         "issue": "Queries timing out under load",
            ...         "tried": ["Added indexes", "Query optimization", "Connection pooling"],
            ...         "energy": "low",
            ...         "impact": "Blocking production deployment"
            ...     }
            ... )
        """
        # Validate inputs
        self._validate_inputs(goal, message_type, audience, tone)

        # Get user preferences and resolve effective tone
        preferences = session_manager.get_user_preferences()
        effective_tone = tone or preferences.tone

        # Normalize context
        context = context or {}

        # Log operation start with rich metadata
        self.logger.logger.info(
            "Starting message draft",
            extra={
                "goal": goal[:50],
                "message_type": message_type,
                "audience": audience,
                "tone": effective_tone,
                "has_context": bool(context),
            },
        )

        try:
            # Try LLM generation with timeout
            result = await with_timeout(
                self._generate_with_llm(
                    goal, message_type, audience, effective_tone, context, preferences
                ),
                timeout_seconds=self.settings.llm_timeout_seconds,
                operation_name="liaison_llm_generation",
            )

            # Mark success and track metrics
            self._record_success_metrics(
                message_type, audience, effective_tone, result, "llm"
            )

            return result

        except (ProviderError, EmptyResponseError, Exception) as e:
            # LLM failed - use graceful degradation
            self.logger.logger.warning(
                f"LLM generation failed, using template fallback: {e}",
                extra={"error_type": type(e).__name__},
            )

            self.metrics["llm_failures"] += 1
            self.metrics["template_fallbacks"] += 1

            # Generate using template fallback
            result = self._generate_with_template(
                goal, message_type, audience, effective_tone, context
            )

            self._record_success_metrics(
                message_type, audience, effective_tone, result, "template"
            )

            return result

    def _validate_inputs(
        self,
        goal: str,
        message_type: str,
        audience: str,
        tone: Optional[str],
    ) -> None:
        """
        Validate input parameters with helpful error messages.

        Raises detailed AgentValidationError with suggestions for fixing issues.
        """
        # Validate goal
        if not goal or not goal.strip():
            raise AgentValidationError(
                "Goal cannot be empty. Provide a brief description of what you're communicating about.",
                agent_name="liaison",
            )

        if len(goal) > 500:
            raise AgentValidationError(
                f"Goal is too long ({len(goal)} chars). Keep it under 500 characters for best results.",
                agent_name="liaison",
            )

        # Validate message_type
        valid_types = set(MessageType)
        if message_type not in valid_types:
            raise AgentValidationError(
                f"Invalid message_type '{message_type}'. "
                f"Must be one of: {', '.join(valid_types)}",
                agent_name="liaison",
            )

        # Validate audience
        valid_audiences = set(Audience)
        if audience not in valid_audiences:
            raise AgentValidationError(
                f"Invalid audience '{audience}'. "
                f"Must be one of: {', '.join(valid_audiences)}",
                agent_name="liaison",
            )

        # Validate tone if provided
        if tone is not None:
            valid_tones = set(Tone)
            if tone not in valid_tones:
                raise AgentValidationError(
                    f"Invalid tone '{tone}'. "
                    f"Must be one of: {', '.join(valid_tones)} or None to use user preference",
                    agent_name="liaison",
                )

    async def _generate_with_llm(
        self,
        goal: str,
        message_type: str,
        audience: str,
        tone: str,
        context: Dict[str, Any],
        preferences: Any,
    ) -> Dict[str, Any]:
        """
        Generate message using LLM with advanced prompt engineering.

        Uses few-shot learning and structured prompting for high-quality output.
        """
        # Build comprehensive system prompt
        system_prompt = self._build_system_prompt(message_type, audience, tone)

        # Build user prompt with few-shot examples
        user_prompt = self._build_user_prompt(
            goal, message_type, audience, tone, context, preferences
        )

        # Prepare messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # Call LLM
        response = await chat_model(messages)

        # Parse and validate response
        result = self._parse_and_validate_llm_response(response, tone)

        return result

    def _build_system_prompt(
        self, message_type: str, audience: str, tone: str
    ) -> str:
        """
        Build comprehensive system prompt with role definition and guidelines.

        This prompt teaches the LLM how to communicate effectively for the
        specific audience, tone, and message type.
        """
        # Audience-specific context
        audience_guidance = {
            "manager": "someone who needs visibility into decisions, outcomes, and timeline. Focus on impact and next steps.",
            "teammate": "a peer who understands technical context and can help collaborate. Be specific and share relevant details.",
            "client": "an external stakeholder who values clarity and professionalism. Focus on delivered value and clear next steps.",
            "public": "a general audience requiring accessible, jargon-free communication. Be clear and welcoming.",
        }

        # Tone-specific guidance
        tone_guidance = {
            "professional": "Use formal language, proper structure, and professional terminology. Be comprehensive but concise.",
            "casual": "Be friendly and conversational while remaining clear and respectful. Show personality but stay professional.",
            "direct": "Be extremely concise and to-the-point. Minimize pleasantries. Lead with the most important information.",
        }

        # Message type-specific guidelines
        type_guidelines = {
            "status_update": """
Structure:
1. Current status headline
2. What's been accomplished
3. What's in progress
4. Any blockers or concerns
5. Clear next steps
6. Timeline update if relevant""",
            "proposal": """
Structure:
1. The problem or opportunity
2. Proposed solution/approach
3. Key benefits and trade-offs
4. Alternatives considered (briefly)
5. What you need (decision, feedback, resources)
6. Suggested timeline""",
            "progress": """
Structure:
1. Overall progress summary (percentage if known)
2. Completed milestones/deliverables
3. Current focus areas
4. Remaining work
5. Timeline status (on track, ahead, behind)
6. Any risks or changes""",
            "help_request": """
Structure:
1. What you're trying to achieve
2. The specific problem or blocker
3. What you've already tried
4. The impact or urgency
5. Specific help you need
6. Acknowledge constraints (time, energy) if relevant

Important: Make it easy to say yes. Be specific about what help looks like.""",
            "delegation": """
Structure:
1. The task/request clearly stated
2. Context and why it matters
3. Why this person is well-suited
4. Success criteria
5. Timeline and priority level
6. Resources and support available
7. Make yourself available for questions""",
        }

        # Neurodiverse-friendly communication principles
        neurodiverse_guidelines = """
Neurodiverse-Friendly Communication Principles:
- Use clear, unambiguous language - avoid idioms and unclear references
- Provide explicit structure with headers, bullets, or numbered lists
- Be direct about expectations and requests
- Acknowledge capacity and energy levels when mentioned
- Frame asks in low-anxiety ways (e.g., "when you have time" not "urgent ASAP")
- Specify concrete next steps rather than vague intentions
- Be honest about uncertainty - don't over-promise
- Avoid performative positivity - be genuine and realistic
"""

        return f"""You are an expert communication assistant helping draft a {message_type} message.

TARGET AUDIENCE: {audience}
{audience_guidance.get(audience, "")}

COMMUNICATION TONE: {tone}
{tone_guidance.get(tone, "")}

MESSAGE TYPE GUIDELINES for {message_type}:
{type_guidelines.get(message_type, "")}

{neurodiverse_guidelines}

OUTPUT FORMAT:
Return a valid JSON object with these exact fields:
{{
    "subject": "Clear, specific subject line (max 80 chars, or null if not applicable)",
    "message": "The complete message body, well-structured with appropriate formatting",
    "tone": "{tone}"
}}

Focus on clarity, authenticity, and providing value to the recipient.
Use the structure guidelines above but adapt naturally - don't be overly formulaic."""

    def _build_user_prompt(
        self,
        goal: str,
        message_type: str,
        audience: str,
        tone: str,
        context: Dict[str, Any],
        preferences: Any,
    ) -> str:
        """
        Build user prompt with few-shot examples and current request.

        Few-shot learning significantly improves output quality by showing
        the LLM concrete examples of the desired style and structure.
        """
        # Include relevant few-shot examples if available
        examples_section = ""
        if message_type in FEW_SHOT_EXAMPLES:
            tone_examples = FEW_SHOT_EXAMPLES[message_type].get(tone)
            if tone_examples:
                examples_section = f"""Here's an example of a great {message_type} message with {tone} tone:

INPUT: {tone_examples['input']}

OUTPUT: {json.dumps(tone_examples['output'], indent=2)}

---

"""

        # Format context into readable bullet points
        context_lines = []
        if context:
            context_lines.append("Additional context:")
            for key, value in context.items():
                if isinstance(value, list):
                    context_lines.append(f"  - {key}: {', '.join(str(v) for v in value)}")
                else:
                    context_lines.append(f"  - {key}: {value}")
        context_section = "\n".join(context_lines) if context_lines else "No additional context provided"

        return f"""{examples_section}Now draft a {message_type} message with these parameters:

GOAL/TOPIC: {goal}
AUDIENCE: {audience}
TONE: {tone}

{context_section}

USER PREFERENCES: {preferences.to_prompt_context()}

Generate an appropriate message following the system guidelines and example above.
Return valid JSON with subject, message, and tone fields exactly as specified."""

    def _parse_and_validate_llm_response(
        self, response: str, expected_tone: str
    ) -> Dict[str, Any]:
        """
        Parse LLM response and validate it meets quality requirements.

        Raises:
            EmptyResponseError: If response is empty or invalid
            json.JSONDecodeError: If response isn't valid JSON
        """
        # Try to parse as JSON
        try:
            result = json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response if it's wrapped in text
            import re

            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                raise EmptyResponseError(
                    "LLM response is not valid JSON and couldn't be parsed"
                )

        # Validate required fields
        if "message" not in result:
            raise EmptyResponseError("LLM response missing 'message' field")

        message = result.get("message", "").strip()
        if not message:
            raise EmptyResponseError("LLM returned empty message")

        if len(message) < 20:
            raise EmptyResponseError(
                f"Generated message too short ({len(message)} chars)"
            )

        # Enrich with metadata
        return {
            "subject": result.get("subject"),
            "message": message,
            "tone": result.get("tone", expected_tone),
            "estimated_tokens": self._estimate_tokens(response),
            "metadata": {
                "generation_method": "llm",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message_length": len(message),
            },
        }

    def _generate_with_template(
        self,
        goal: str,
        message_type: str,
        audience: str,
        tone: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Graceful degradation: Generate message using templates when LLM fails.

        This ensures the agent always returns something useful, even during
        LLM outages or failures. Templates are simple but functional.
        """
        # Get template
        templates = FALLBACK_TEMPLATES.get(message_type, {})
        template = templates.get(
            tone,
            "Subject: Update on {goal}\n\nStatus update regarding {goal}.\n\nCurrent status: {status}\nNext steps: {next_steps}",
        )

        # Prepare template variables with safe defaults
        template_vars = {
            "goal": goal,
            "status": context.get("status", "in progress"),
            "completed": self._format_list(context.get("completed", ["ongoing work"])),
            "in_progress": self._format_list(
                context.get("in_progress", ["current tasks"])
            ),
            "blockers": self._format_list(context.get("blockers", ["none"])),
            "next_steps": self._format_list(
                context.get("next_steps", ["continue development"])
            ),
            "timeline": context.get("timeline", "ongoing"),
        }

        # Format message from template
        try:
            full_message = template.format(**template_vars)
            # Split subject and message if template includes both
            if full_message.startswith("Subject:"):
                lines = full_message.split("\n", 1)
                subject = lines[0].replace("Subject:", "").strip()
                message = lines[1].strip() if len(lines) > 1 else full_message
            else:
                subject = f"Update: {goal[:50]}"
                message = full_message
        except KeyError as e:
            # Fallback to absolute minimum if template variables don't match
            subject = f"Update: {goal[:50]}"
            message = f"Update regarding {goal}.\n\nStatus: {context.get('status', 'in progress')}"

        return {
            "subject": subject,
            "message": message,
            "tone": tone,
            "estimated_tokens": self._estimate_tokens(message),
            "metadata": {
                "generation_method": "template_fallback",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message_length": len(message),
            },
        }

    def _format_list(self, items: Any) -> str:
        """Format list items for template substitution."""
        if isinstance(items, list):
            return ", ".join(str(item) for item in items) if items else "none"
        return str(items)

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for cost awareness.

        Uses conservative heuristic: ~4 characters per token for English.
        For production, consider integrating tiktoken for accurate counts.
        """
        # Conservative estimate: 4 chars per token
        return max(len(text) // 4, 1)

    def _record_success_metrics(
        self,
        message_type: str,
        audience: str,
        tone: str,
        result: Dict[str, Any],
        method: str,
    ) -> None:
        """
        Record comprehensive metrics for observability and monitoring.

        Tracks success rates, token usage, and breakdowns by various dimensions.
        """
        # Update counters
        self.metrics["messages_drafted"] += 1
        self.metrics["total_tokens"] += result.get("estimated_tokens", 0)

        # Track by message type
        if message_type not in self.metrics["message_types"]:
            self.metrics["message_types"][message_type] = 0
        self.metrics["message_types"][message_type] += 1

        # Track by audience
        if audience not in self.metrics["audience_breakdown"]:
            self.metrics["audience_breakdown"][audience] = 0
        self.metrics["audience_breakdown"][audience] += 1

        # Track by tone
        if tone not in self.metrics["tone_breakdown"]:
            self.metrics["tone_breakdown"][tone] = 0
        self.metrics["tone_breakdown"][tone] += 1

        # Persist to memory for future reference and learning
        self._persist_to_memory(message_type, result, method)

        # Log success with rich metadata
        self.logger.logger.info(
            "Message drafted successfully",
            extra={
                "message_type": message_type,
                "audience": audience,
                "tone": tone,
                "tokens": result.get("estimated_tokens"),
                "method": method,
                "message_length": result.get("metadata", {}).get("message_length", 0),
            },
        )

    def _persist_to_memory(
        self, message_type: str, result: Dict[str, Any], method: str
    ) -> None:
        """
        Persist drafted message to vector memory for future learning.

        Failures here don't block message generation - we log and continue.
        """
        try:
            mem.batch.add_data_object(
                {
                    "role": "liaison",
                    "message_type": message_type,
                    "subject": result.get("subject", ""),
                    "message": result["message"],
                    "tone": result["tone"],
                    "generation_method": method,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                "Memory",
            )
        except Exception as e:
            # Don't fail message drafting if memory persistence fails
            self.logger.logger.warning(
                f"Failed to persist message to memory: {e}",
                extra={"error_type": type(e).__name__},
            )

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics for monitoring and observability.

        Returns:
            Dictionary containing:
                - messages_drafted: Total messages generated
                - total_tokens: Cumulative token usage estimate
                - errors: Total errors encountered
                - retries: Number of retry attempts
                - llm_failures: LLM generation failures
                - template_fallbacks: Times graceful degradation was used
                - message_types: Breakdown by message type
                - audience_breakdown: Breakdown by audience
                - tone_breakdown: Breakdown by tone
                - success_rate: Percentage of successful generations
                - avg_tokens_per_message: Average token usage
        """
        metrics = self.metrics.copy()

        # Calculate derived metrics
        total_attempts = metrics["messages_drafted"] + metrics["errors"]
        if total_attempts > 0:
            metrics["success_rate"] = (
                metrics["messages_drafted"] / total_attempts
            ) * 100
        else:
            metrics["success_rate"] = 0.0

        if metrics["messages_drafted"] > 0:
            metrics["avg_tokens_per_message"] = (
                metrics["total_tokens"] / metrics["messages_drafted"]
            )
        else:
            metrics["avg_tokens_per_message"] = 0.0

        return metrics

    def reset_metrics(self) -> None:
        """Reset metrics (useful for testing and monitoring period resets)."""
        self.metrics = {
            "messages_drafted": 0,
            "total_tokens": 0,
            "errors": 0,
            "retries": 0,
            "llm_failures": 0,
            "template_fallbacks": 0,
            "message_types": {},
            "audience_breakdown": {},
            "tone_breakdown": {},
        }

    # Backward compatibility with old interface
    def draft_message_sync(self, goal: str) -> str:
        """
        Synchronous version for backward compatibility with legacy code.

        This is a simple stub that returns a basic message without LLM.
        For full functionality, use the async draft_message method.
        """
        return f"Status update: planning work on '{goal}'."
