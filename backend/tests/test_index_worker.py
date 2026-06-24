"""Tests for MemoryIndexWorker: pending→ready, retries, batch, recovery."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from desktopclaw.agent.memory.graph import MemoryGraphStore
from desktopclaw.agent.memory.graph_builder import GraphBuilder
from desktopclaw.agent.memory.index_worker import MemoryIndexWorker
from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore
from desktopclaw.agent.memory.types import ReasoningUnit
from desktopclaw.config.schema import MemoryConfig


def _make_unit(uid: str, title: str = "T", status: str = "pending") -> ReasoningUnit:
    return ReasoningUnit(
        id=uid, title=title, description="d", content="c",
        domain="general", created_at="2026-01-01T00:00:00Z",
        index_status=status,  # type: ignore[arg-type]
    )


def _build_worker(tmp_path: Path, embedder=None) -> tuple[MemoryIndexWorker, ReasoningBankStore]:
    cfg = MemoryConfig(
        enabled=True,
        index_worker_enabled=True,
        index_worker_interval_s=0.05,
        embedding_batch_size=4,
        index_max_retries=2,
    )
    if embedder is None:
        embedder = MagicMock()
        embedder.embed_document.return_value = [0.1, 0.2]
        embedder.embed_document_batch.side_effect = lambda texts: [[0.1, 0.2]] * len(texts)
    bank = ReasoningBankStore(tmp_path / "bank.json")
    graph = MemoryGraphStore(tmp_path / "g.db")
    builder = GraphBuilder(graph, embedder)
    return MemoryIndexWorker(bank, builder, embedder, cfg), bank


@pytest.mark.asyncio
async def test_pending_to_ready(tmp_path: Path) -> None:
    worker, bank = _build_worker(tmp_path)
    bank.add_unit(_make_unit("u1"))
    worker.enqueue("u1")
    worker.start()
    # Allow the worker to process.
    await asyncio.sleep(0.3)
    await worker.stop()

    unit = bank.get_by_id("u1")
    assert unit is not None
    assert unit.index_status == "ready"
    assert unit.embedding == [0.1, 0.2]
    assert unit.embedding_model == worker.config.embedding_model
    assert unit.embedding_dim == 2


@pytest.mark.asyncio
async def test_failure_retry_then_failed(tmp_path: Path) -> None:
    embedder = MagicMock()
    # Always fails.
    embedder.embed_document.side_effect = RuntimeError("model broken")
    embedder.embed_document_batch.side_effect = lambda texts: [[0.1, 0.2]] * len(texts)
    worker, bank = _build_worker(tmp_path, embedder=embedder)
    bank.add_unit(_make_unit("u1"))
    worker.enqueue("u1")
    worker.start()
    await asyncio.sleep(1.0)
    await worker.stop()

    unit = bank.get_by_id("u1")
    assert unit is not None
    # After index_max_retries (2) attempts, marked failed.
    assert unit.index_status == "failed"
    assert "model broken" in unit.index_error
    assert unit.index_attempts >= 2


@pytest.mark.asyncio
async def test_batch_processing(tmp_path: Path) -> None:
    worker, bank = _build_worker(tmp_path)
    for i in range(5):
        bank.add_unit(_make_unit(f"u{i}"))
        worker.enqueue(f"u{i}")
    worker.start()
    await asyncio.sleep(0.5)
    await worker.stop()

    for i in range(5):
        unit = bank.get_by_id(f"u{i}")
        assert unit is not None
        assert unit.index_status == "ready"


@pytest.mark.asyncio
async def test_recover_pending_on_startup(tmp_path: Path) -> None:
    bank_file = tmp_path / "bank.json"
    bank = ReasoningBankStore(bank_file)
    # Persist a pending unit from a "previous run".
    bank.add_unit(_make_unit("leftover"))
    assert bank.get_by_id("leftover").index_status == "pending"

    # New worker instance, fresh process — recover_pending re-enqueues.
    cfg = MemoryConfig(
        enabled=True, index_worker_interval_s=0.05, index_max_retries=2,
    )
    embedder = MagicMock()
    embedder.embed_document.return_value = [0.5]
    embedder.embed_document_batch.side_effect = lambda texts: [[0.5]] * len(texts)
    graph = MemoryGraphStore(tmp_path / "g.db")
    builder = GraphBuilder(graph, embedder)
    worker = MemoryIndexWorker(bank, builder, embedder, cfg)
    recovered = worker.recover_pending()
    assert recovered == 1
    worker.start()
    await asyncio.sleep(0.3)
    await worker.stop()
    assert bank.get_by_id("leftover").index_status == "ready"


@pytest.mark.asyncio
async def test_reindex_all_marks_pending(tmp_path: Path) -> None:
    worker, bank = _build_worker(tmp_path)
    # A "ready" unit from an old model.
    bank.add_unit(ReasoningUnit(
        id="old", title="T", description="d", content="c",
        embedding=[1.0, 0.0], index_status="ready",
        embedding_model="all-MiniLM-L6-v2", embedding_dim=2,
        created_at="2026-01-01T00:00:00Z",
    ))
    count = await worker.reindex_all()
    assert count == 1
    unit = bank.get_by_id("old")
    assert unit.index_status == "pending"
    assert unit.embedding is None
    assert unit.embedding_model == ""


@pytest.mark.asyncio
async def test_enqueue_idempotent(tmp_path: Path) -> None:
    worker, bank = _build_worker(tmp_path)
    worker.enqueue("u1")
    worker.enqueue("u1")
    assert worker._queue.qsize() == 1


@pytest.mark.asyncio
async def test_ready_unit_not_reindexed(tmp_path: Path) -> None:
    worker, bank = _build_worker(tmp_path)
    bank.add_unit(ReasoningUnit(
        id="u1", title="T", description="d", content="c",
        embedding=[0.9], index_status="ready", embedding_model="X", embedding_dim=1,
        created_at="2026-01-01T00:00:00Z",
    ))
    worker.enqueue("u1")
    worker.start()
    await asyncio.sleep(0.2)
    await worker.stop()
    # Embedder not called because unit was already ready (filtered in _index_batch).
    worker.embedder.embed_document.assert_not_called()
