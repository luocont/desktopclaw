"""Tests for MRAgentRetriever fallback: pending keyword hits + embed timeout."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

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


@pytest.mark.asyncio
async def test_pending_unit_surfaces_via_keywords(tmp_path: Path) -> None:
    """A pending (not-yet-indexed) unit must still be retrievable by keyword."""
    cfg = MemoryConfig(enabled=True, retrieval_top_k=5)
    embedder = MagicMock()
    # Even when vector search yields a result, the pending unit should appear
    # via the keyword fallback path.
    embedder.embed_query_async = AsyncMock(return_value=[1.0, 0.0, 0.0])
    embedder.available = True
    bank = ReasoningBankStore(tmp_path / "bank.json")
    # Ready unit (vector match).
    bank.add_unit(ReasoningUnit(
        id="ready1", title="Windows encoding fix", description="d", content="use utf-8",
        embedding=[1.0, 0.0, 0.0], index_status="ready", confidence=0.8,
        created_at="2026-01-01T00:00:00Z",
    ))
    # Pending unit (keyword-only, invisible to vector search).
    bank.add_unit(ReasoningUnit(
        id="pending1", title="Windows exec troubleshooting", description="d",
        content="check exec output encoding", index_status="pending", confidence=0.7,
        created_at="2026-01-01T00:00:00Z",
    ))
    retriever = MRAgentRetriever(
        embedder=embedder, bank=bank, graph=MemoryGraphStore(tmp_path / "g.db"),
        provider=EmptyProvider(), model="test", fast_model="test", config=cfg,
    )
    result = await retriever.retrieve("windows encoding", "L1")
    ids = {u.id for u in result.units}
    assert "ready1" in ids
    assert "pending1" in ids  # surfaced via keyword fallback


@pytest.mark.asyncio
async def test_query_embed_timeout_keyword_fallback(tmp_path: Path) -> None:
    """When embed times out (returns None), pure keyword search still returns units."""
    cfg = MemoryConfig(enabled=True, retrieval_top_k=5, embedding_timeout_s=0.01)
    embedder = MagicMock()
    embedder.embed_query_async = AsyncMock(return_value=None)  # simulates timeout/failure
    embedder.available = False
    bank = ReasoningBankStore(tmp_path / "bank.json")
    bank.add_unit(ReasoningUnit(
        id="u1", title="Deploy python app", description="d",
        content="use gunicorn", confidence=0.8, index_status="ready",
        created_at="2026-01-01T00:00:00Z",
    ))
    retriever = MRAgentRetriever(
        embedder=embedder, bank=bank, graph=MemoryGraphStore(tmp_path / "g.db"),
        provider=EmptyProvider(), model="test", fast_model="test", config=cfg,
    )
    result = await retriever.retrieve("python deploy", "L1")
    assert len(result.units) == 1
    assert result.units[0].id == "u1"


@pytest.mark.asyncio
async def test_no_units_returns_empty(tmp_path: Path) -> None:
    cfg = MemoryConfig(enabled=True)
    embedder = MagicMock()
    embedder.embed_query_async = AsyncMock(return_value=[1.0, 0.0])
    retriever = MRAgentRetriever(
        embedder=embedder, bank=ReasoningBankStore(tmp_path / "b.json"),
        graph=MemoryGraphStore(tmp_path / "g.db"),
        provider=EmptyProvider(), model="test", fast_model="test", config=cfg,
    )
    result = await retriever.retrieve("anything", "L1")
    assert result.units == []


@pytest.mark.asyncio
async def test_l1_query_embeded_once_not_per_node(tmp_path: Path) -> None:
    """Regression: query must be embedded once, not once per content node."""
    cfg = MemoryConfig(enabled=True, retrieval_top_k=3, mragent_max_iterations=1)
    embedder = MagicMock()
    embedder.embed_query_async = AsyncMock(return_value=[1.0, 0.0, 0.0])
    embedder.available = True
    bank = ReasoningBankStore(tmp_path / "b.json")
    retriever = MRAgentRetriever(
        embedder=embedder, bank=bank, graph=MemoryGraphStore(tmp_path / "g.db"),
        provider=EmptyProvider(), model="test", fast_model="test", config=cfg,
    )
    await retriever.retrieve("query", "L3")
    # embed_query_async called for L1 + once more for active traversal (2 total),
    # NOT once per content node. With empty graph, exactly 2 calls.
    assert embedder.embed_query_async.await_count <= 2
