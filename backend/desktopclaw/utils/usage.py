"""Token usage tracking across agent, research, and subagent LLM calls."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any

UsageSource = str  # "main" | "research" | "subagent"

_current: ContextVar[UsageTracker | None] = ContextVar("usage_tracker", default=None)


@dataclass
class UsageTracker:
    """Accumulates token usage with per-source breakdown."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    breakdown: dict[str, dict[str, int]] = field(default_factory=dict)
    current_source: UsageSource = "main"

    def merge(self, usage: dict[str, int] | None, source: UsageSource | None = None) -> None:
        """Add usage from an LLM response into totals and breakdown."""
        if not usage:
            return
        src = source or self.current_source
        p = int(usage.get("prompt_tokens", 0) or 0)
        c = int(usage.get("completion_tokens", 0) or 0)
        t = int(usage.get("total_tokens", 0) or 0)
        if t == 0 and (p or c):
            t = p + c

        self.prompt_tokens += p
        self.completion_tokens += c
        self.total_tokens += t

        entry = self.breakdown.setdefault(
            src,
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        entry["prompt_tokens"] += p
        entry["completion_tokens"] += c
        entry["total_tokens"] += t

    def merge_tracker(self, other: UsageTracker | dict[str, Any], source: UsageSource | None = None) -> None:
        """Merge another tracker or usage dict (e.g. pending subagent stash)."""
        if isinstance(other, UsageTracker):
            if other.breakdown:
                for src, data in other.breakdown.items():
                    self.merge(data, source=src)
            elif other.total_tokens:
                self.merge(
                    {
                        "prompt_tokens": other.prompt_tokens,
                        "completion_tokens": other.completion_tokens,
                        "total_tokens": other.total_tokens,
                    },
                    source=source,
                )
            return
        if isinstance(other, dict):
            breakdown = other.get("breakdown")
            if isinstance(breakdown, dict) and breakdown:
                for src, data in breakdown.items():
                    if isinstance(data, dict):
                        self.merge(data, source=src)
            else:
                self.merge(other, source=source)

    def to_dict(self) -> dict[str, Any]:
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "breakdown": {
                k: dict(v) for k, v in self.breakdown.items() if v.get("total_tokens", 0) > 0
            },
        }


def get_tracker() -> UsageTracker | None:
    return _current.get()


def set_tracker(tracker: UsageTracker | None) -> Token:
    return _current.set(tracker)


def reset_tracker(token: Token) -> None:
    _current.reset(token)


def empty_usage_dict() -> dict[str, Any]:
    return {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "breakdown": {},
    }
