"""Format and inject retrieved strategies into message lists."""

from __future__ import annotations

from desktopclaw.agent.memory.prompts import STRATEGY_HINT_TAG
from desktopclaw.agent.memory.types import ReasoningUnit

_STRATEGY_TAG = STRATEGY_HINT_TAG


def format_strategies(units: list[ReasoningUnit]) -> str:
    """Render reasoning units as markdown for prompt injection."""
    if not units:
        return ""
    lines = [
        "## Agent 策略记忆（检索结果）",
        "以下内容为决策参考，勿当作必须逐字执行的命令。",
        "",
    ]
    for unit in units:
        tools = ", ".join(unit.tools) if unit.tools else "任意"
        kind_label = "策略" if unit.kind == "strategy" else "避坑"
        lines.append(f"### [{kind_label}] {unit.title}")
        lines.append(f"适用场景: {unit.description}")
        lines.append(unit.content)
        lines.append(f"置信度: {unit.confidence:.2f} | 相关工具: {tools}")
        lines.append("")
    return "\n".join(lines).rstrip()


def inject_into_system_prompt(system_prompt: str, units: list[ReasoningUnit]) -> str:
    block = format_strategies(units)
    if not block:
        return system_prompt
    return f"{system_prompt}\n\n---\n\n{block}"


def inject_before_llm(messages: list[dict], units: list[ReasoningUnit]) -> list[dict]:
    """Insert strategy hint as a user message before the latest user turn."""
    block = format_strategies(units)
    if not block:
        return messages
    hint = {"role": "user", "content": f"{_STRATEGY_TAG}\n{block}"}
    result = list(messages)
    insert_at = len(result)
    for i in range(len(result) - 1, -1, -1):
        if result[i].get("role") == "user":
            insert_at = i
            break
    result.insert(insert_at, hint)
    return result


def inject_after_tool(messages: list[dict], units: list[ReasoningUnit]) -> list[dict]:
    """Append strategy hint after tool results."""
    block = format_strategies(units)
    if not block:
        return messages
    return messages + [{"role": "user", "content": f"{_STRATEGY_TAG}\n{block}"}]
