"""Tests for graph builder."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from desktopclaw.agent.memory.graph import MemoryGraphStore
from desktopclaw.agent.memory.graph_builder import GraphBuilder
from desktopclaw.agent.memory.types import ReasoningUnit


@pytest.fixture
def builder(tmp_path: Path) -> GraphBuilder:
    embedder = MagicMock()
    embedder.embed_document.return_value = [1.0, 0.0]
    # Batch must return one vector per input text — mirror the input length.
    embedder.embed_document_batch.side_effect = lambda texts: [[1.0, 0.0]] * len(texts)
    return GraphBuilder(MemoryGraphStore(tmp_path / "g.db"), embedder)


def test_incremental_update_creates_nodes(builder: GraphBuilder) -> None:
    unit = ReasoningUnit(
        id="unit-1",
        title="Windows UTF-8 encoding",
        description="Fix garbled exec output",
        content="Set PYTHONIOENCODING=utf-8",
        domain="shell",
        tools=["exec"],
        created_at="2026-01-01T00:00:00Z",
    )
    builder.incremental_update(unit)
    content_nodes = builder.graph.get_content_nodes_for_unit("unit-1")
    assert len(content_nodes) == 1
    assert "UTF-8" in content_nodes[0].text


def test_rebuild_updates_existing(builder: GraphBuilder) -> None:
    unit = ReasoningUnit(
        id="u2", title="Cron setup", description="d", content="c",
        domain="automation", created_at="2026-01-01T00:00:00Z",
    )
    builder.incremental_update(unit)
    builder.incremental_update(unit)
    assert len(builder.graph.list_content_nodes()) == 1
