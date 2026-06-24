"""Tests for MemoryGraphStore."""

from pathlib import Path

import pytest

from desktopclaw.agent.memory.graph import MemoryGraphStore
from desktopclaw.agent.memory.types import GraphEdge, GraphNode


@pytest.fixture
def graph(tmp_path: Path) -> MemoryGraphStore:
    return MemoryGraphStore(tmp_path / "graph.db")


def test_upsert_and_get_node(graph: MemoryGraphStore) -> None:
    node = GraphNode(id="cue-1", node_type="cue", text="windows", unit_id="u1")
    graph.upsert_node(node)
    loaded = graph.get_node("cue-1")
    assert loaded is not None
    assert loaded.text == "windows"


def test_neighbors(graph: MemoryGraphStore) -> None:
    graph.upsert_node(GraphNode(id="cue-1", node_type="cue", text="a", unit_id="u1"))
    graph.upsert_node(GraphNode(id="tag-1", node_type="tag", text="shell", unit_id=None))
    graph.add_edge(GraphEdge("cue-1", "tag-1", "activates"))
    neighbors = graph.get_neighbors("cue-1", "out")
    assert len(neighbors) == 1
    assert neighbors[0].id == "tag-1"


def test_delete_unit_nodes(graph: MemoryGraphStore) -> None:
    graph.upsert_node(GraphNode(id="c1", node_type="content", text="body", unit_id="u1"))
    graph.upsert_node(GraphNode(id="cue-u1", node_type="cue", text="kw", unit_id="u1"))
    graph.delete_unit_nodes("u1")
    assert graph.get_node("c1") is None
    assert graph.get_node("cue-u1") is None
