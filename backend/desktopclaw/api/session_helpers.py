"""Helpers for exposing session history to the frontend UI."""

from __future__ import annotations

from typing import Any

from desktopclaw.session.manager import Session
from desktopclaw.session.ui_messages import messages_to_ui_blocks, turn_messages_to_ui_blocks

__all__ = [
    "messages_to_ui_blocks",
    "session_message_for_ui",
    "session_messages_for_ui",
    "session_info_dict",
    "turn_messages_to_ui_blocks",
]


def session_message_for_ui(msg: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a single backend session message (legacy flat shape)."""
    blocks = messages_to_ui_blocks([msg])
    return blocks[0] if blocks else None


def session_messages_for_ui(session: Session) -> list[dict[str, Any]]:
    """Return display-safe messages for the chat UI."""
    return messages_to_ui_blocks(session.messages)


def session_info_dict(session: Session) -> dict[str, Any]:
    """Serialize session metadata for list endpoints."""
    return {
        "key": session.key,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
        "message_count": len(session.messages),
    }
