"""Agent collaboration protocol for intra-workflow coordination."""

from .context import SharedContext
from .messages import CollaborationMessage, MessageType

__all__ = [
    "CollaborationMessage",
    "MessageType",
    "SharedContext",
]
