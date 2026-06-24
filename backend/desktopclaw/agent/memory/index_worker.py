"""Background batch indexer for pending ReasoningUnits.

Lifecycle of a distilled strategy unit on the warm/cold paths:

    distiller writes unit (embedding=None, index_status="pending")
        → worker.enqueue(unit_id)            [fire-and-forget]
    worker batch: embed_document → graph_builder → mark "ready"
        on failure: index_status="failed" with retry + backoff

The worker holds an ``asyncio.Lock`` around JSON writes so distill-time appends
and index-time updates never corrupt ``reasoning_bank.json``.

On startup it scans the bank for any ``pending``/``failed`` units and reindexes
them — so a crash mid-index is recovered automatically on next boot.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from desktopclaw.agent.memory.embedder import LocalEmbedder
    from desktopclaw.agent.memory.graph_builder import GraphBuilder
    from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore
    from desktopclaw.config.schema import MemoryConfig


class MemoryIndexWorker:
    """Background batch indexer for pending ReasoningUnits."""

    def __init__(
        self,
        bank: ReasoningBankStore,
        graph_builder: GraphBuilder,
        embedder: LocalEmbedder,
        config: MemoryConfig,
    ):
        self.bank = bank
        self.graph_builder = graph_builder
        self.embedder = embedder
        self.config = config
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._write_lock = asyncio.Lock()
        self._stop = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._enqueued: set[str] = set()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def enqueue(self, unit_id: str) -> None:
        """Schedule a unit for background indexing (idempotent)."""
        if not unit_id or unit_id in self._enqueued:
            return
        self._enqueued.add(unit_id)
        self._queue.put_nowait(unit_id)

    async def preload_embedder(self) -> bool:
        """Warm the embedding model in a worker thread (idempotent)."""
        return await self.embedder.preload()

    async def reindex_all(self) -> int:
        """Mark every unit pending and enqueue it (model-switch migration)."""
        async with self._write_lock:
            for unit in self.bank.list_units():
                unit.index_status = "pending"
                unit.index_error = ""
                unit.index_attempts = 0
                unit.embedding = None
                unit.embedding_model = ""
                unit.embedding_dim = 0
                self.bank.update_unit(unit)
        count = 0
        for unit in self.bank.list_units():
            self.enqueue(unit.id)
            count += 1
        logger.info("Scheduled {} units for full reindex", count)
        return count

    def start(self) -> asyncio.Task:
        """Launch the worker loop as a background task."""
        if self._task is None or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._run(), name="memory-index-worker")
        return self._task

    async def stop(self) -> None:
        """Signal the worker to drain and exit."""
        self._stop.set()
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    def recover_pending(self) -> int:
        """Re-enqueue any pending/failed units left over from a prior run.

        Called once at startup before the loop spins up.
        """
        recovered = 0
        for unit in self.bank.list_pending_units():
            self.enqueue(unit.id)
            recovered += 1
        if recovered:
            logger.info("Recovered {} pending/failed units for indexing", recovered)
        return recovered

    async def recover_failed_after_embedder_ready(self) -> int:
        """Reset failed units and re-enqueue after the embedding model becomes available."""
        recovered = 0
        async with self._write_lock:
            for unit in self.bank.list_units():
                if unit.index_status != "failed":
                    continue
                unit.index_status = "pending"
                unit.index_error = ""
                unit.index_attempts = 0
                self.bank.update_unit(unit)
                recovered += 1
        for unit in self.bank.list_units():
            if unit.index_status == "pending":
                self.enqueue(unit.id)
        if recovered:
            logger.info("Re-queued {} previously failed units after embedder ready", recovered)
        return recovered

    # ------------------------------------------------------------------ #
    # Worker loop
    # ------------------------------------------------------------------ #
    async def _run(self) -> None:
        logger.info("MemoryIndexWorker started")
        while not self._stop.is_set():
            try:
                batch = await self._collect_batch()
                if batch:
                    await self._index_batch(batch)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("IndexWorker iteration failed")
                await asyncio.sleep(1.0)

    async def _collect_batch(self) -> list[str]:
        """Block on the first item, then opportunistically drain up to batch size."""
        try:
            first = await asyncio.wait_for(
                self._queue.get(),
                timeout=self.config.index_worker_interval_s,
            )
        except asyncio.TimeoutError:
            return []
        self._enqueued.discard(first)
        batch = [first]
        while len(batch) < self.config.embedding_batch_size:
            try:
                nxt = self._queue.get_nowait()
                self._enqueued.discard(nxt)
                if nxt not in batch:
                    batch.append(nxt)
            except asyncio.QueueEmpty:
                break
        return batch

    async def _index_batch(self, unit_ids: list[str]) -> None:
        # Snapshot units under the write lock so concurrent distills can't race.
        async with self._write_lock:
            units = [self.bank.get_by_id(uid) for uid in unit_ids]
            units = [u for u in units if u is not None and u.index_status != "ready"]
        if not units:
            return

        retry_ids: list[str] = []
        try:
            retry_ids = await asyncio.to_thread(self._index_units_sync, units)
        except Exception:
            logger.exception("Index batch failed for {} units", len(units))

        # Re-enqueue retries from the async context (the sync helper runs in a
        # worker thread with no event loop, so scheduling must happen here).
        for uid in retry_ids:
            await asyncio.sleep(0)
            self.enqueue(uid)

    def _index_units_sync(self, units: list) -> list[str]:
        """Sync helper running in a worker thread (model calls block).

        Returns the list of unit ids that should be retried (still pending).
        """
        retry_ids: list[str] = []
        for unit in units:
            unit.index_attempts += 1
            try:
                vector = self.embedder.embed_document(unit.search_text())
                if vector is None:
                    raise RuntimeError("embedder unavailable (no model loaded)")
                unit.embedding = vector
                unit.embedding_model = self.config.embedding_model
                unit.embedding_dim = len(vector)
                unit.index_status = "ready"
                unit.index_error = ""
                self.graph_builder.incremental_update(unit)
                logger.debug("Indexed unit {} (ready)", unit.id)
            except Exception as exc:
                if unit.index_attempts >= self.config.index_max_retries:
                    unit.index_status = "failed"
                    unit.index_error = str(exc)[:500]
                    logger.warning(
                        "Unit {} indexing failed after {} attempts: {}",
                        unit.id, unit.index_attempts, exc,
                    )
                else:
                    # Keep pending; caller re-enqueues for a backoff retry.
                    unit.index_status = "pending"
                    unit.index_error = str(exc)[:500]
                    retry_ids.append(unit.id)
            finally:
                self.bank.update_unit(unit)
        return retry_ids
