from datetime import date, datetime, timezone
from enum import StrEnum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import uuid


class Priority(StrEnum):
    critical = "P0"
    high = "P1"
    medium = "P2"
    low = "P3"


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str
    detail: str
    priority: Priority
    estimate_h: int = Field(gt=0)
    done: bool = False


class Sprint(BaseModel):
    name: str
    start: date
    end: date
    tasks: list[Task]


class MessageRole(StrEnum):
    user = "user"
    assistant = "assistant"
    system = "system"


class ConversationMessage(BaseModel):
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


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
    user_id: str = Field(default="default")  # single user for now
    sprint_length_weeks: int = 2
    priority_system: str = "P0-P3"  # could be "NOW-NEXT-LATER" etc
    tone: str = "professional"  # professional, casual, motivational
    work_hours_per_week: int = 40
    preferred_task_size: str = "medium"  # small, medium, large
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
    answers: Dict[str, str]  # question -> answer mapping
