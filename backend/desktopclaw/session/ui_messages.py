"""Convert raw session messages into frontend UI blocks."""

from __future__ import annotations

import json
import re
from typing import Any

_THINKING_TAG_RE = re.compile(
    r"<think>([\s\S]*?)</think>",
    re.IGNORECASE,
)


def _normalize_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(p for p in parts if p)
    return str(content)


def _extract_thinking(msg: dict[str, Any]) -> str | None:
    reasoning = msg.get("reasoning_content")
    if reasoning and str(reasoning).strip():
        return str(reasoning).strip()
    content = _normalize_content(msg.get("content", ""))
    match = _THINKING_TAG_RE.search(content)
    if match:
        return match.group(1).strip()
    return None


def _parse_tool_args(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {"raw": raw}
        except json.JSONDecodeError:
            return {"raw": raw}
    return {}


def _tool_summary(name: str, args: dict[str, Any]) -> str:
    if name == "spawn":
        label = args.get("label") or str(args.get("task", ""))[:40]
        return f"子任务: {label}" if label else "spawn"
    val = next((v for v in args.values() if isinstance(v, str)), None)
    if val:
        short = f'{val[:40]}…' if len(val) > 40 else val
        return f'{name}("{short}")'
    return name


def _tool_block_type(name: str) -> str:
    return "subagent" if name == "spawn" else "tool"


def messages_to_ui_blocks(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert raw session messages into frontend UI blocks."""
    out: list[dict[str, Any]] = []
    pending_tool_blocks: dict[str, int] = {}
    i = 0

    while i < len(messages):
        msg = messages[i]
        role = msg.get("role", "")

        if role == "system":
            i += 1
            continue

        if role == "user":
            content = _normalize_content(msg.get("content", ""))
            if content:
                out.append({"role": "user", "content": content})
            i += 1
            continue

        if role == "assistant":
            thinking = _extract_thinking(msg)
            if thinking:
                out.append({
                    "role": "ai",
                    "blockType": "thinking",
                    "content": thinking,
                    "collapsed": True,
                })

            tool_calls = msg.get("tool_calls") or []
            content = _normalize_content(msg.get("content", ""))

            if tool_calls:
                for tc in tool_calls:
                    func = tc.get("function", {}) if isinstance(tc, dict) else {}
                    name = func.get("name", "tool")
                    args = _parse_tool_args(func.get("arguments", "{}"))
                    block_type = _tool_block_type(name)
                    block: dict[str, Any] = {
                        "role": "ai",
                        "blockType": block_type,
                        "content": _tool_summary(name, args),
                        "collapsed": True,
                        "meta": {"name": name, "args": args},
                    }
                    if args.get("label"):
                        block["meta"]["label"] = args["label"]
                    out.append(block)
                    tc_id = tc.get("id") if isinstance(tc, dict) else None
                    if tc_id:
                        pending_tool_blocks[tc_id] = len(out) - 1
                i += 1
                continue

            if content:
                out.append({
                    "role": "ai",
                    "blockType": "reply",
                    "content": content,
                })
            i += 1
            continue

        if role == "tool":
            tc_id = msg.get("tool_call_id")
            result = _normalize_content(msg.get("content", ""))
            name = msg.get("name", "tool")
            if tc_id and tc_id in pending_tool_blocks:
                idx = pending_tool_blocks[tc_id]
                out[idx].setdefault("meta", {})["result"] = result
                if name == "spawn":
                    out[idx]["blockType"] = "subagent"
            else:
                block_type = _tool_block_type(name)
                out.append({
                    "role": "ai",
                    "blockType": block_type,
                    "content": result or name,
                    "collapsed": True,
                    "meta": {"name": name, "result": result},
                })
            i += 1
            continue

        i += 1

    return out


def turn_messages_to_ui_blocks(turn_messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert one agent turn's raw messages into UI blocks for SSE complete."""
    return messages_to_ui_blocks(turn_messages)
