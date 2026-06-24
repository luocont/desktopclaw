"""Dynamic memory retrieval trigger rules."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from desktopclaw.agent.memory.prompts import STRATEGY_HINT_TAG
from desktopclaw.agent.memory.types import TriggerLevel

_ERROR_MARKERS = re.compile(
    r"\b(error|failed|failure|exception|traceback|not found|permission denied|timeout)\b",
    re.IGNORECASE,
)


@dataclass
class TriggerState:
    """Tracks tool failure patterns within one agent loop."""

    consecutive_tool_errors: dict[str, int] = field(default_factory=dict)
    last_tool_name: str | None = None
    pending_retrieval: TriggerLevel | None = None

    def record_tool_result(self, tool_name: str, result: str) -> TriggerLevel | None:
        """Update state after a tool call; return trigger level if retrieval needed."""
        if _ERROR_MARKERS.search(result or ""):
            self.consecutive_tool_errors[tool_name] = self.consecutive_tool_errors.get(tool_name, 0) + 1
            count = self.consecutive_tool_errors[tool_name]
            if count >= 2:
                return "L3"
            return "L2"
        self.consecutive_tool_errors[tool_name] = 0
        return None

    def consume_pending(self) -> TriggerLevel | None:
        level = self.pending_retrieval
        self.pending_retrieval = None
        return level


def task_start_level() -> TriggerLevel:
    return "L1"


def subagent_start_level() -> TriggerLevel:
    return "L2"


def should_retrieve_before_llm(state: TriggerState) -> TriggerLevel | None:
    return state.consume_pending()


def extract_query_from_messages(messages: list[dict]) -> str:
    """Build a retrieval query from recent conversation context."""
    parts: list[str] = []
    for msg in reversed(messages):
        role = msg.get("role")
        content = msg.get("content")
        if role == "user" and isinstance(content, str):
            if content.startswith("[Runtime Context"):
                continue
            if content.startswith(STRATEGY_HINT_TAG):
                continue
            parts.append(content)
            if len(parts) >= 2:
                break
        elif role == "tool" and isinstance(content, str) and _ERROR_MARKERS.search(content):
            parts.append(f"Tool error: {content[:500]}")
            break
    return "\n".join(reversed(parts)) if parts else ""
