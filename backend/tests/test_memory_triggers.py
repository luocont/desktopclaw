"""Tests for memory triggers and injection."""

from desktopclaw.agent.context import ContextBuilder
from desktopclaw.agent.memory.injector import format_strategies, inject_before_llm
from desktopclaw.agent.memory.triggers import TriggerState, extract_query_from_messages
from desktopclaw.agent.memory.types import ReasoningUnit


def test_trigger_state_escalates_on_repeated_errors() -> None:
    state = TriggerState()
    assert state.record_tool_result("exec", "command failed with error") == "L2"
    assert state.record_tool_result("exec", "another error") == "L3"


def test_trigger_state_resets_on_success() -> None:
    state = TriggerState()
    state.record_tool_result("exec", "error happened")
    assert state.record_tool_result("exec", "ok output") is None
    assert state.consecutive_tool_errors["exec"] == 0


def test_format_strategies() -> None:
    units = [
        ReasoningUnit(
            id="1", title="Test", description="When testing", content="Do X",
            kind="strategy", tools=["exec"], confidence=0.9, created_at="",
        ),
    ]
    text = format_strategies(units)
    assert "Agent 策略记忆" in text
    assert "[策略] Test" in text


def test_inject_before_llm_preserves_roles() -> None:
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
    ]
    units = [
        ReasoningUnit(
            id="1", title="H", description="D", content="C", created_at="",
        ),
    ]
    result = inject_before_llm(messages, units)
    assert result[0]["role"] == "system"
    assert result[-1]["role"] == "user"
    assert any(ContextBuilder.STRATEGY_HINT_TAG in m.get("content", "") for m in result if m["role"] == "user")


def test_extract_query_from_messages() -> None:
    messages = [
        {"role": "user", "content": "fix my script"},
        {"role": "assistant", "content": "ok"},
        {"role": "tool", "content": "Error: file not found"},
    ]
    q = extract_query_from_messages(messages)
    assert "fix my script" in q or "Error" in q
