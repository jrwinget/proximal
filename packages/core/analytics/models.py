"""Pydantic v2 models for analytics data."""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TaskCompletion(BaseModel):
    """A recorded task completion event.

    Parameters
    ----------
    id : str
        Auto-generated 8-char hex identifier.
    task_id : str
        Reference to the originating task.
    title : str
        Human-readable task title.
    predicted_hours : float
        Original time estimate in hours.
    actual_hours : float
        Actual time spent in hours.
    completed_at : str
        ISO-8601 timestamp of completion.
    energy_level : str
        User's energy level at completion (low/medium/high).
    session_id : str
        The session during which the task was completed.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    task_id: str
    title: str
    predicted_hours: float
    actual_hours: float
    completed_at: str
    energy_level: str
    session_id: str


class FocusSessionRecord(BaseModel):
    """A recorded focus (pomodoro-style) session.

    Parameters
    ----------
    id : str
        Auto-generated 8-char hex identifier.
    task_id : str
        Reference to the task being worked on.
    planned_duration_min : int
        Planned session length in minutes.
    actual_duration_min : int
        Actual session length in minutes.
    completed : bool
        Whether the full session was completed.
    interrupted : bool
        Whether the session was interrupted.
    started_at : str
        ISO-8601 timestamp of session start.
    ended_at : str or None
        ISO-8601 timestamp of session end, if finished.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    task_id: str
    planned_duration_min: int
    actual_duration_min: int
    completed: bool
    interrupted: bool
    started_at: str
    ended_at: Optional[str] = None


class EnergySnapshot(BaseModel):
    """A point-in-time energy level observation.

    Parameters
    ----------
    id : str
        Auto-generated 8-char hex identifier.
    recorded_at : str
        ISO-8601 timestamp of the snapshot.
    energy_level : str
        Energy level at the time (low/medium/high).
    notes : str
        Optional free-text notes.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    recorded_at: str
    energy_level: str
    notes: str = ""
