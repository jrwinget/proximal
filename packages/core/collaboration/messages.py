"""Collaboration message types for agent-to-agent communication."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MessageType(StrEnum):
    """Types of collaboration messages between agents."""

    request = "request"
    response = "response"
    signal = "signal"
    handoff = "handoff"


class CollaborationMessage(BaseModel):
    """A message sent from one agent to another within a workflow.

    Parameters
    ----------
    id : str
        Auto-generated 8-char hex identifier.
    source_agent : str
        Name of the sending agent.
    target_agent : str
        Name of the receiving agent (or "*" for broadcast).
    message_type : MessageType
        The type of message.
    payload : dict
        Arbitrary payload data.
    timestamp : datetime
        When the message was created.
    """

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    source_agent: str
    target_agent: str = "*"
    message_type: MessageType = MessageType.signal
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
