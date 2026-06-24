"""Tests for MRAgentRetriever (mocked LLM)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from desktopclaw.agent.memory.embedder import LocalEmbedder
from desktopclaw.agent.memory.graph import MemoryGraphStore
from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore
from desktopclaw.agent.memory.retriever import MRAgentRetriever
from desktopclaw.agent.memory.types import ReasoningUnit
from desktopclaw.config.schema import MemoryConfig
from desktopclaw.providers.base import LLMProvider, LLMResponse


class EmptyProvider(LLMProvider):
    async def chat(self, *args, **kwargs) -> LLMResponse:
        return LLMResponse(content="", tool_calls=[])

    def get_default_model(self) -> str:
        return "test"


@pytest.fixture
def retriever(tmp_path: Path) -> MRAgentRetriever:
    cfg = MemoryConfig(enabled=True, retrieval_top_k=2)
    embedder = MagicMock()
    embedder.embed.return_value = [1.0, 0.0, 0.0]
    embedder.embed_query_async = AsyncMock(return_value=[1.0, 0.0, 0.0])
    embedder.available = True
    bank = ReasoningBankStore(tmp_path / "bank.json")
    bank.add_unit(ReasoningUnit(
        id="1", title="Windows fix", description="encoding", content="use utf-8",
        embedding=[1.0, 0.0, 0.0], confidence=0.8, created_at="2026-01-01T00:00:00Z",
        index_status="ready",
    ))
    graph = MemoryGraphStore(tmp_path / "g.db")
    return MRAgentRetriever(
        embedder=embedder,
        bank=bank,
        graph=graph,
        provider=EmptyProvider(),
        model="test",
        fast_model="test",
        config=cfg,
    )


@pytest.mark.asyncio
async def test_l1_retrieval(retriever: MRAgentRetriever) -> None:
    result = await retriever.retrieve("windows encoding problem", "L1")
    assert len(result.units) >= 1
    assert result.units[0].title == "Windows fix"


@pytest.mark.asyncio
async def test_disabled_returns_empty(tmp_path: Path) -> None:
    cfg = MemoryConfig(enabled=False)
    r = MRAgentRetriever(
        embedder=MagicMock(),
        bank=ReasoningBankStore(tmp_path / "b.json"),
        graph=MemoryGraphStore(tmp_path / "g.db"),
        provider=EmptyProvider(),
        model="test",
        fast_model="test",
        config=cfg,
    )
    result = await r.retrieve("query", "L1")
    assert result.units == []
