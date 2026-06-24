"""Factory for wiring agent memory services."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from desktopclaw.agent.memory.distiller import StrategyDistiller
from desktopclaw.agent.memory.embedder import LocalEmbedder
from desktopclaw.agent.memory.graph import MemoryGraphStore
from desktopclaw.agent.memory.graph_builder import GraphBuilder
from desktopclaw.agent.memory.index_worker import MemoryIndexWorker
from desktopclaw.agent.memory.migration import ensure_memory_layout, migrate_embedding_model
from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore
from desktopclaw.agent.memory.retriever import MRAgentRetriever
from desktopclaw.config.schema import MemoryConfig

if TYPE_CHECKING:
    from desktopclaw.providers.base import LLMProvider


@dataclass
class AgentMemoryServices:
    """Bundle of agent strategy memory components."""

    retriever: MRAgentRetriever | None
    distiller: StrategyDistiller | None
    embedder: LocalEmbedder | None
    index_worker: MemoryIndexWorker | None
    config: MemoryConfig


def build_memory_services(
    workspace: Path,
    provider: LLMProvider,
    model: str,
    fast_model: str,
    config: MemoryConfig,
) -> AgentMemoryServices:
    """Initialize memory layout and construct retriever/distiller if enabled."""
    memory_dir = ensure_memory_layout(workspace)
    if not config.enabled:
        return AgentMemoryServices(
            retriever=None, distiller=None, embedder=None, index_worker=None, config=config,
        )

    embedder = LocalEmbedder(config, workspace)
    bank = ReasoningBankStore(memory_dir / "reasoning_bank.json")
    # Model-switch migration: stale units (wrong model/dim) → pending, reindexed
    # by the worker's recover_pending() on startup.
    try:
        migrate_embedding_model(memory_dir, config.embedding_model, config.embedding_truncate_dim)
    except Exception:
        from loguru import logger
        logger.exception("Embedding model migration check failed; continuing")
    graph = MemoryGraphStore(memory_dir / "graph.db")
    graph_builder = GraphBuilder(graph, embedder)

    index_worker = (
        MemoryIndexWorker(bank, graph_builder, embedder, config)
        if config.index_worker_enabled
        else None
    )

    retriever = MRAgentRetriever(
        embedder=embedder,
        bank=bank,
        graph=graph,
        provider=provider,
        model=model,
        fast_model=fast_model or model,
        config=config,
    )
    distiller = StrategyDistiller(
        bank=bank,
        graph_builder=graph_builder,
        embedder=embedder,
        provider=provider,
        model=model,
        config=config,
        index_worker=index_worker,
    )
    return AgentMemoryServices(
        retriever=retriever,
        distiller=distiller,
        embedder=embedder,
        index_worker=index_worker,
        config=config,
    )
