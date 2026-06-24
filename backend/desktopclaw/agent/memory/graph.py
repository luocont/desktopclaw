"""SQLite graph store for MRAgent Cue-Tag-Content memory."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from desktopclaw.agent.memory.types import GraphEdge, GraphNode, NodeType


class MemoryGraphStore:
    """Persistent directed graph for memory nodes."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    node_type TEXT NOT NULL,
                    text TEXT NOT NULL,
                    unit_id TEXT,
                    embedding TEXT
                );
                CREATE TABLE IF NOT EXISTS edges (
                    src_id TEXT NOT NULL,
                    dst_id TEXT NOT NULL,
                    relation TEXT NOT NULL DEFAULT 'links',
                    PRIMARY KEY (src_id, dst_id, relation)
                );
                CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
                CREATE INDEX IF NOT EXISTS idx_nodes_unit ON nodes(unit_id);
                CREATE INDEX IF NOT EXISTS idx_edges_src ON edges(src_id);
                CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges(dst_id);
            """)

    def upsert_node(self, node: GraphNode) -> None:
        embedding_json = json.dumps(node.embedding) if node.embedding else None
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO nodes (id, node_type, text, unit_id, embedding)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    node_type=excluded.node_type,
                    text=excluded.text,
                    unit_id=excluded.unit_id,
                    embedding=excluded.embedding
                """,
                (node.id, node.node_type, node.text, node.unit_id, embedding_json),
            )

    def add_edge(self, edge: GraphEdge) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO edges (src_id, dst_id, relation)
                VALUES (?, ?, ?)
                """,
                (edge.src_id, edge.dst_id, edge.relation),
            )

    def get_node(self, node_id: str) -> GraphNode | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,)).fetchone()
        if not row:
            return None
        return self._row_to_node(row)

    def _row_to_node(self, row: sqlite3.Row) -> GraphNode:
        embedding = json.loads(row["embedding"]) if row["embedding"] else None
        return GraphNode(
            id=row["id"],
            node_type=row["node_type"],
            text=row["text"],
            unit_id=row["unit_id"],
            embedding=embedding,
        )

    def find_nodes_by_type(self, node_type: NodeType) -> list[GraphNode]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE node_type = ?", (node_type,)
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def find_nodes_by_text_contains(self, substring: str, node_type: NodeType | None = None) -> list[GraphNode]:
        pattern = f"%{substring.lower()}%"
        with self._connect() as conn:
            if node_type:
                rows = conn.execute(
                    "SELECT * FROM nodes WHERE node_type = ? AND LOWER(text) LIKE ?",
                    (node_type, pattern),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM nodes WHERE LOWER(text) LIKE ?",
                    (pattern,),
                ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def get_neighbors(self, node_id: str, direction: str = "out") -> list[GraphNode]:
        with self._connect() as conn:
            if direction == "out":
                rows = conn.execute(
                    """
                    SELECT n.* FROM nodes n
                    JOIN edges e ON e.dst_id = n.id
                    WHERE e.src_id = ?
                    """,
                    (node_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT n.* FROM nodes n
                    JOIN edges e ON e.src_id = n.id
                    WHERE e.dst_id = ?
                    """,
                    (node_id,),
                ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def get_content_nodes_for_unit(self, unit_id: str) -> list[GraphNode]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM nodes WHERE unit_id = ? AND node_type = 'content'",
                (unit_id,),
            ).fetchall()
        return [self._row_to_node(r) for r in rows]

    def delete_unit_nodes(self, unit_id: str) -> None:
        with self._connect() as conn:
            node_ids = [
                r["id"]
                for r in conn.execute("SELECT id FROM nodes WHERE unit_id = ?", (unit_id,)).fetchall()
            ]
            for nid in node_ids:
                conn.execute("DELETE FROM edges WHERE src_id = ? OR dst_id = ?", (nid, nid))
            conn.execute("DELETE FROM nodes WHERE unit_id = ?", (unit_id,))

    def list_content_nodes(self) -> list[GraphNode]:
        return self.find_nodes_by_type("content")
