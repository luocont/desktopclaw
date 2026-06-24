"""Tests for StrategyDistiller — async indexing decoupling."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from desktopclaw.agent.memory.distiller import StrategyDistiller
from desktopclaw.agent.memory.graph import MemoryGraphStore
from desktopclaw.agent.memory.graph_builder import GraphBuilder
from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore
from desktopclaw.config.schema import MemoryConfig
from desktopclaw.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class ScriptProvider(LLMProvider):
    def __init__(self, response: LLMResponse):
        super().__init__()
        self._response = response

    async def chat(self, *args, **kwargs) -> LLMResponse:
        return self._response

    def get_default_model(self) -> str:
        return "test"


@pytest.fixture
def distiller(tmp_path: Path) -> StrategyDistiller:
    embedder = MagicMock()
    embedder.embed.return_value = [1.0, 0.0]
    bank = ReasoningBankStore(tmp_path / "bank.json")
    # Use a mock graph_builder so we can assert it is NOT called on the hot path.
    builder = MagicMock()
    return StrategyDistiller(
        bank=bank,
        graph_builder=builder,
        embedder=embedder,
        provider=MagicMock(),
        model="test",
        config=MemoryConfig(enabled=True, distillation=True, distillation_min_confidence=0.6),
    )


@pytest.mark.asyncio
async def test_distill_persists_high_confidence_units(distiller: StrategyDistiller) -> None:
    tool_response = LLMResponse(
        content=None,
        tool_calls=[
            ToolCallRequest(
                id="1",
                name="save_reasoning_units",
                arguments={
                    "units": [{
                        "title": "Verify path exists",
                        "description": "Before editing files",
                        "content": "Use read_file first",
                        "kind": "strategy",
                        "domain": "files",
                        "tools": ["read_file"],
                    }],
                    "task_outcome": "success",
                    "confidence": 0.85,
                },
            ),
        ],
    )
    distiller.provider = ScriptProvider(tool_response)
    distiller.provider.chat_with_retry = AsyncMock(return_value=tool_response)

    await distiller.distill_from_turn(
        "sess", "edit config", [{"role": "user", "content": "edit config"}], ["read_file"],
    )
    units = distiller.bank.list_units()
    assert len(units) == 1
    # No synchronous embed on the hot path: unit written as pending, no embedding.
    assert units[0].index_status == "pending"
    assert units[0].embedding is None
    distiller.embedder.embed.assert_not_called()
    distiller.graph_builder.incremental_update.assert_not_called()


@pytest.mark.asyncio
async def test_low_confidence_skipped(distiller: StrategyDistiller) -> None:
    tool_response = LLMResponse(
        content=None,
        tool_calls=[
            ToolCallRequest(
                id="1",
                name="save_reasoning_units",
                arguments={"units": [], "task_outcome": "success", "confidence": 0.3},
            ),
        ],
    )
    distiller.provider = ScriptProvider(tool_response)
    distiller.provider.chat_with_retry = AsyncMock(return_value=tool_response)

    await distiller.distill_from_turn("s", "hi", [], [])
    assert len(distiller.bank.list_units()) == 0


@pytest.mark.asyncio
async def test_distill_enqueues_index_worker(tmp_path: Path) -> None:
    """Distilled units must be enqueued to the background indexer (fire-and-forget)."""
    embedder = MagicMock()
    bank = ReasoningBankStore(tmp_path / "bank.json")
    graph = MemoryGraphStore(tmp_path / "g.db")
    builder = GraphBuilder(graph, embedder)
    worker = MagicMock()
    worker.enqueue = MagicMock()

    distiller = StrategyDistiller(
        bank=bank,
        graph_builder=builder,
        embedder=embedder,
        provider=MagicMock(),
        model="test",
        config=MemoryConfig(enabled=True, distillation=True, distillation_min_confidence=0.6),
        index_worker=worker,
    )
    tool_response = LLMResponse(
        content=None,
        tool_calls=[
            ToolCallRequest(
                id="1",
                name="save_reasoning_units",
                arguments={
                    "units": [{
                        "title": "T", "description": "d", "content": "c",
                        "kind": "strategy",
                    }],
                    "task_outcome": "success",
                    "confidence": 0.9,
                },
            ),
        ],
    )
    distiller.provider = ScriptProvider(tool_response)
    distiller.provider.chat_with_retry = AsyncMock(return_value=tool_response)

    await distiller.distill_from_turn("s", "task", [{"role": "user", "content": "task"}], [])
    assert worker.enqueue.called
    enqueued_id = worker.enqueue.call_args[0][0]
    assert enqueued_id  # non-empty
    # The enqueued id matches the persisted unit.
    assert distiller.bank.get_by_id(enqueued_id) is not None
