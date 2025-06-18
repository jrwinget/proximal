from datetime import date
from enum import StrEnum
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
