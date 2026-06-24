"""Tests for token usage tracking across agent, research, and subagent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from desktopclaw.agent.loop import AgentLoop, ProcessResult
from desktopclaw.agent.subagent import SubagentManager
from desktopclaw.agent.tools.deep_web_search import DeepWebSearchTool
from desktopclaw.bus.events import InboundMessage
from desktopclaw.bus.queue import MessageBus
from desktopclaw.providers.base import LLMProvider, LLMResponse
from desktopclaw.utils.usage import UsageTracker, get_tracker, reset_tracker, set_tracker


def test_usage_tracker_merge_and_breakdown() -> None:
    tracker = UsageTracker()
    tracker.merge({"prompt_tokens": 100, "completion_tokens": 40, "total_tokens": 140}, source="main")
    tracker.merge({"prompt_tokens": 500, "completion_tokens": 200, "total_tokens": 700}, source="research")

    assert tracker.prompt_tokens == 600
    assert tracker.completion_tokens == 240
    assert tracker.total_tokens == 840
    assert tracker.breakdown["main"]["total_tokens"] == 140
    assert tracker.breakdown["research"]["total_tokens"] == 700


def test_usage_tracker_merge_tracker_with_breakdown() -> None:
    left = UsageTracker()
    left.merge({"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}, source="main")
    right = UsageTracker()
    right.merge({"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28}, source="subagent")

    combined = UsageTracker()
    combined.merge_tracker(left.to_dict())
    combined.merge_tracker(right.to_dict())

    assert combined.total_tokens == 43
    assert combined.breakdown["main"]["total_tokens"] == 15
    assert combined.breakdown["subagent"]["total_tokens"] == 28


@pytest.mark.asyncio
async def test_chat_with_retry_records_usage_when_tracker_set() -> None:
    class _Provider(LLMProvider):
        async def chat(self, *args, **kwargs) -> LLMResponse:
            return LLMResponse(
                content="ok",
                usage={"prompt_tokens": 12, "completion_tokens": 8, "total_tokens": 20},
            )

        def get_default_model(self) -> str:
            return "test"

    tracker = UsageTracker()
    token = set_tracker(tracker)
    try:
        provider = _Provider()
        await provider.chat_with_retry(messages=[{"role": "user", "content": "hi"}])
        assert tracker.total_tokens == 20
        assert tracker.breakdown["main"]["total_tokens"] == 20
    finally:
        reset_tracker(token)


def _make_provider(usage: dict | None = None) -> LLMProvider:
    class _Provider(LLMProvider):
        async def chat(self, *args, **kwargs) -> LLMResponse:
            return LLMResponse(
                content="done",
                usage=usage or {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40},
            )

        def get_default_model(self) -> str:
            return "test-model"

    return _Provider()


def _make_loop(tmp_path) -> AgentLoop:
    provider = _make_provider()
    loop = AgentLoop(
        bus=MessageBus(),
        provider=provider,
        workspace=tmp_path,
        model="test-model",
    )
    loop.tools.get_definitions = MagicMock(return_value=[])
    loop._connect_mcp = AsyncMock(return_value=None)  # type: ignore[method-assign]
    return loop


@pytest.mark.asyncio
async def test_run_agent_loop_returns_usage(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    messages = [{"role": "user", "content": "hello"}]

    content, tools_used, all_msgs, usage, _hit_max, _llm_error = await loop._run_agent_loop(messages)

    assert content == "done"
    assert usage["total_tokens"] == 40
    assert usage["breakdown"]["main"]["total_tokens"] == 40
    assert get_tracker() is None


@pytest.mark.asyncio
async def test_process_direct_returns_process_result(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    loop.memory_consolidator.maybe_consolidate_by_tokens = AsyncMock(return_value=None)  # type: ignore[method-assign]

    result = await loop.process_direct("hello", session_key="cli:test")

    assert isinstance(result, ProcessResult)
    assert result.content == "done"
    assert result.usage["total_tokens"] == 40


@pytest.mark.asyncio
async def test_deep_web_search_tags_research_source() -> None:
    from desktopclaw.agent.research.state import ResearchReport

    async def fake_run(**kwargs):
        tracker = get_tracker()
        assert tracker is not None
        assert tracker.current_source == "research"
        tracker.merge({"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150}, source="research")
        return ResearchReport(question="q", markdown="## 调研摘要\nok")

    research_loop = MagicMock()
    research_loop.run = fake_run
    tool = DeepWebSearchTool(research_loop=research_loop)

    tracker = UsageTracker()
    token = set_tracker(tracker)
    try:
        await tool.execute(query="test question")
        assert tracker.breakdown["research"]["total_tokens"] == 150
        assert tracker.current_source == "main"
    finally:
        reset_tracker(token)


@pytest.mark.asyncio
async def test_subagent_stash_and_pop_pending_usage(tmp_path) -> None:
    bus = MessageBus()
    provider = _make_provider(usage={"prompt_tokens": 60, "completion_tokens": 20, "total_tokens": 80})

    manager = SubagentManager(
        provider=provider,
        workspace=tmp_path,
        bus=bus,
        model="test-model",
    )

    await manager._run_subagent(
        task_id="t1",
        task="do work",
        label="work",
        origin={"channel": "api", "chat_id": "frontend"},
        session_key="api:frontend",
    )

    pending = manager.pop_pending_usage("api:frontend")
    assert pending["total_tokens"] == 80
    assert pending["breakdown"]["subagent"]["total_tokens"] == 80
    assert manager.pop_pending_usage("api:frontend") == {}


@pytest.mark.asyncio
async def test_system_message_merges_subagent_pending_usage(tmp_path) -> None:
    loop = _make_loop(tmp_path)
    loop.memory_consolidator.maybe_consolidate_by_tokens = AsyncMock(return_value=None)  # type: ignore[method-assign]

    pending = UsageTracker()
    pending.merge({"prompt_tokens": 60, "completion_tokens": 20, "total_tokens": 80}, source="subagent")
    loop.subagents._pending_usage["api:frontend"] = pending

    msg = InboundMessage(
        channel="system",
        sender_id="subagent",
        chat_id="api:frontend",
        content="[Subagent completed]\n\nResult:\nDone",
    )

    response = await loop._process_message(msg)

    assert response is not None
    usage = response.metadata["usage"]
    assert usage["total_tokens"] == 120
    assert usage["breakdown"]["main"]["total_tokens"] == 40
    assert usage["breakdown"]["subagent"]["total_tokens"] == 80


def test_build_complete_event_process_result() -> None:
    from desktopclaw.api.server import APIServer

    event = APIServer._build_complete_event(
        ProcessResult(
            content="hello",
            usage={"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3, "breakdown": {}},
        )
    )
    assert event["response"] == "hello"
    assert event["usage"]["total_tokens"] == 3
    assert event["success"] is True
    assert "error" not in event


def test_build_complete_event_llm_error() -> None:
    from desktopclaw.api.server import APIServer

    event = APIServer._build_complete_event(
        ProcessResult(
            content="Error calling LLM: auth failed",
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "breakdown": {}},
            error="Error calling LLM: auth failed",
        )
    )
    assert event["success"] is False
    assert event["error"] == "Error calling LLM: auth failed"
