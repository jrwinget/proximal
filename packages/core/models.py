from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
import uuid


class Priority(StrEnum):
    critical = "P0"
    high = "P1"
    medium = "P2"
    low = "P3"


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


class ClarificationRequest(BaseModel):
    questions: List[str]
    context: Optional[str] = None


class ClarificationResponse(BaseModel):
    answers: Dict[str, str]
