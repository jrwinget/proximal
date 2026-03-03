from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Any, Optional, List, Dict
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator
import uuid


class Priority(StrEnum):
    critical = "P0"
    high = "P1"
    medium = "P2"
    low = "P3"


class EnergyLevel(StrEnum):
    """User's current energy/capacity level for adaptive planning."""

    low = "low"
    medium = "medium"
    high = "high"


class EnergyConfig(BaseModel):
    """Configuration that adapts planning behaviour to the user's energy level.

    Parameters
    ----------
    max_task_duration_minutes : int
        Maximum duration for any single task in minutes.
    break_frequency : int
        Number of tasks between mandatory breaks.
    session_duration_minutes : int
        Length of a focus session in minutes.
    max_daily_hours : float
        Maximum work hours to schedule per day.
    task_complexity : str
        Allowed complexity ceiling ("simple", "moderate", "complex").
    tone : str
        Communication tone for LLM prompts ("gentle", "balanced", "direct").
    """

    max_task_duration_minutes: int
    break_frequency: int
    session_duration_minutes: int
    max_daily_hours: float
    task_complexity: str
    tone: str

    @classmethod
    def for_level(cls, level: EnergyLevel) -> "EnergyConfig":
        """Return a pre-built config for a given energy level.

        Parameters
        ----------
        level : EnergyLevel
            The energy level to build a config for.

        Returns
        -------
        EnergyConfig
            Configuration tuned to the requested energy level.
        """
        configs = {
            EnergyLevel.low: cls(
                max_task_duration_minutes=15,
                break_frequency=2,
                session_duration_minutes=15,
                max_daily_hours=2.0,
                task_complexity="simple",
                tone="gentle",
            ),
            EnergyLevel.medium: cls(
                max_task_duration_minutes=45,
                break_frequency=4,
                session_duration_minutes=25,
                max_daily_hours=5.0,
                task_complexity="moderate",
                tone="balanced",
            ),
            EnergyLevel.high: cls(
                max_task_duration_minutes=120,
                break_frequency=6,
                session_duration_minutes=50,
                max_daily_hours=8.0,
                task_complexity="complex",
                tone="direct",
            ),
        }
        return configs[level]


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    # task titles should be concise but meaningful, max 200 chars
    title: str = Field(min_length=1, max_length=200)
    # detailed descriptions can be longer, max 5000 chars
    detail: str = Field(min_length=1, max_length=5000)
    priority: Priority
    # reasonable estimate cap: max 1000 hours (25 work weeks) prevents unrealistic values
    estimate_h: int = Field(gt=0, le=1000)
    done: bool = False

    @field_validator("title", "detail")
    @classmethod
    def validate_not_whitespace(cls, v: str, info) -> str:
        """ensure strings contain actual content, not just whitespace"""
        if not v or not v.strip():
            field_name = info.field_name.replace("_", " ").title()
            raise ValueError(f"{field_name} Cannot Be Empty Or Whitespace Only")
        return v.strip()


class Sprint(BaseModel):
    # sprint names should be brief and descriptive, max 100 chars
    name: str = Field(min_length=1, max_length=100)
    start: date
    end: date
    tasks: list[Task]

    @field_validator("name")
    @classmethod
    def validate_name_not_whitespace(cls, v: str) -> str:
        """ensure sprint name contains actual content, not just whitespace"""
        if not v or not v.strip():
            raise ValueError("Sprint Name Cannot Be Empty Or Whitespace Only")
        return v.strip()

    @model_validator(mode="after")
    def validate_dates(self) -> "Sprint":
        """ensure start date is before end date for logical sprint periods"""
        if self.start >= self.end:
            raise ValueError("Sprint Start Date Must Be Before End Date")
        return self


class MessageRole(StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ConversationMessage(BaseModel):
    role: MessageRole
    # conversation messages can be lengthy but need limits, max 50000 chars
    content: str = Field(min_length=1, max_length=50000)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("content")
    @classmethod
    def validate_content_not_whitespace(cls, v: str) -> str:
        """ensure message content is not just whitespace"""
        if not v or not v.strip():
            raise ValueError("Message Content Cannot Be Empty Or Whitespace Only")
        return v.strip()


class ConversationState(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    messages: List[ConversationMessage] = []
    goal: Optional[str] = None
    clarification_count: int = 0
    max_clarifications: int = 2
    status: str = "active"  # active, planning, completed
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def add_message(self, role: MessageRole, content: str):
        self.messages.append(ConversationMessage(role=role, content=content))
        self.updated_at = datetime.now(timezone.utc)

    def get_context(self, max_messages: int = 10) -> List[Dict[str, str]]:
        """Get recent conversation context for LLM prompts"""
        recent = (
            self.messages[-max_messages:]
            if len(self.messages) > max_messages
            else self.messages
        )
        return [{"role": msg.role, "content": msg.content} for msg in recent]


class UserPreferences(BaseModel):
    user_id: str = Field(default="default")
    sprint_length_weeks: int = 2
    priority_system: str = "P0-P3"
    tone: str = "professional"
    work_hours_per_week: int = 40
    preferred_task_size: str = "medium"
    include_breaks: bool = True
    timezone: str = "UTC"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_prompt_context(self) -> str:
        """Convert preferences to a string for LLM context"""
        return (
            f"User preferences: {self.sprint_length_weeks}-week sprints, "
            f"{self.tone} tone, {self.work_hours_per_week} hours/week available, "
            f"prefers {self.preferred_task_size} task sizes"
        )


class UserProfile(BaseModel):
    """Extended user profile for neurodiverse-aware planning.

    Parameters
    ----------
    user_id : str
        Auto-generated 8-char hex identifier.
    name : str
        Display name; defaults to "Friend".
    focus_style : str
        One of "hyperfocus", "variable", "short-burst".
    transition_difficulty : str
        How hard task-switching is: "low", "moderate", "high".
    time_blindness : str
        Severity of time blindness: "low", "moderate", "high".
    decision_fatigue : str
        Susceptibility to decision fatigue: "low", "moderate", "high".
    overwhelm_threshold : int
        Maximum number of visible tasks before overwhelm.
    peak_hours : list[int]
        Hours of the day (0-23) when energy is highest.
    low_energy_days : list[str]
        Days of the week that tend to be low energy.
    max_daily_hours : float
        Maximum productive hours per day.
    preferred_session_minutes : int
        Preferred focus session length in minutes.
    tone : str
        Communication tone: "warm", "professional", "direct", "playful".
    verbosity : str
        Output detail level: "minimal", "medium", "detailed".
    celebration_style : str
        How to acknowledge accomplishments: "quiet", "enthusiastic", "data-driven".
    """

    user_id: str = Field(default_factory=lambda: uuid4().hex[:8])
    name: str = "Friend"
    focus_style: str = "variable"
    transition_difficulty: str = "moderate"
    time_blindness: str = "moderate"
    decision_fatigue: str = "moderate"
    overwhelm_threshold: int = 5
    peak_hours: list[int] = Field(default_factory=lambda: [10, 11, 14, 15])
    low_energy_days: list[str] = Field(default_factory=list)
    max_daily_hours: float = 6.0
    preferred_session_minutes: int = 25
    tone: str = "warm"
    verbosity: str = "medium"
    celebration_style: str = "quiet"

    def to_prompt_context(self) -> str:
        """Convert profile to a string suitable for LLM system prompts.

        Returns
        -------
        str
            A human-readable summary of the user's profile for prompt injection.
        """
        return (
            f"User profile for {self.name}: "
            f"focus style is {self.focus_style}, "
            f"transition difficulty is {self.transition_difficulty}, "
            f"time blindness is {self.time_blindness}, "
            f"decision fatigue is {self.decision_fatigue}, "
            f"overwhelm threshold is {self.overwhelm_threshold} tasks, "
            f"peak hours are {self.peak_hours}, "
            f"max {self.max_daily_hours} daily hours, "
            f"preferred session length is {self.preferred_session_minutes} minutes, "
            f"tone preference is {self.tone}, "
            f"verbosity is {self.verbosity}, "
            f"celebration style is {self.celebration_style}."
        )


class WellnessObservationType(StrEnum):
    """Types of wellness observations Guardian can record."""

    session_start = "session_start"
    session_end = "session_end"
    break_taken = "break_taken"
    break_skipped = "break_skipped"
    task_completed = "task_completed"
    extended_work = "extended_work"
    late_session = "late_session"


class EscalationLevel(StrEnum):
    """Escalation levels for Guardian interventions."""

    gentle_nudge = "gentle_nudge"
    firm_reminder = "firm_reminder"
    escalated_warning = "escalated_warning"
    session_end_suggestion = "session_end_suggestion"


class WellnessObservation(BaseModel):
    """A single wellness observation recorded by Guardian.

    Parameters
    ----------
    id : str
        Auto-generated 8-char hex identifier.
    user_id : str
        The user this observation belongs to.
    session_id : str
        The session during which this was observed.
    observation_type : WellnessObservationType
        What kind of wellness event was observed.
    data : dict
        Arbitrary payload data.
    timestamp : datetime
        When the observation was made.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    user_id: str = "default"
    session_id: str = ""
    observation_type: WellnessObservationType = WellnessObservationType.session_start
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WellnessInsight(BaseModel):
    """A detected wellness pattern from cross-session analysis."""

    rule_name: str
    severity: EscalationLevel = EscalationLevel.gentle_nudge
    message: str
    data: Dict[str, Any] = Field(default_factory=dict)


class WellnessSessionSummary(BaseModel):
    """Summary of wellness observations for a single session."""

    session_id: str
    user_id: str = "default"
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    tasks_completed: int = 0
    breaks_taken: int = 0
    breaks_skipped: int = 0
    duration_hours: float = 0.0
    was_late_session: bool = False


class ClarificationRequest(BaseModel):
    questions: List[str]
    context: Optional[str] = None


class ClarificationResponse(BaseModel):
    answers: Dict[str, str]
