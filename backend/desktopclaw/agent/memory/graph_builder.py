"""Build MRAgent graph from ReasoningUnit entries.

Called from the cold path (IndexWorker), never the user-facing hot path. Node
embeddings reuse the unit's already-computed embedding where possible and
batch the remaining short-text node embeds to avoid N×serial encode calls.
"""

from __future__ import annotations

import re

from desktopclaw.agent.memory.embedder import LocalEmbedder
from desktopclaw.agent.memory.graph import MemoryGraphStore
from desktopclaw.agent.memory.types import GraphEdge, GraphNode, ReasoningUnit


def _slug(text: str) -> str:
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[\s_]+", "-", cleaned.strip())[:48] or "item"


def _extract_cues(title: str) -> list[str]:
    """Split title into cue keywords."""
    parts = re.split(r"[\s,;/|]+", title.strip())
    cues = [p for p in parts if len(p) > 2]
    return cues[:8] if cues else [title[:32]] if title else ["general"]


class GraphBuilder:
    """Map ReasoningUnit → Cue-Tag-Content graph nodes."""

    def __init__(self, graph: MemoryGraphStore, embedder: LocalEmbedder):
        self.graph = graph
        self.embedder = embedder

    def incremental_update(self, unit: ReasoningUnit) -> None:
        """Add or refresh graph nodes for one reasoning unit.

        Reuses ``unit.embedding`` when present (computed by the IndexWorker) and
        batches the remaining node-text embeds.
        """
        self.graph.delete_unit_nodes(unit.id)

        content_id = f"content-{unit.id}"
        content_text = f"{unit.title}\n{unit.description}\n{unit.content}"
        content_emb = unit.embedding or self.embedder.embed_document(content_text)
        self.graph.upsert_node(GraphNode(
            id=content_id,
            node_type="content",
            text=content_text,
            unit_id=unit.id,
            embedding=content_emb,
        ))

        # Collect the short auxiliary node texts we still need to embed, then
        # batch them so a unit with N cues/tags issues ~1 encode call, not N.
        topic_id = f"topic-{_slug(unit.domain)}"
        tag_texts: list[str] = []
        seen_tags: set[str] = set()
        for t in [unit.domain] + unit.tools + ([unit.kind] if unit.kind else []):
            if t and t not in seen_tags:
                seen_tags.add(t)
                tag_texts.append(t)
        cue_texts = _extract_cues(unit.title)

        aux_texts = [unit.domain] + tag_texts + cue_texts
        aux_embs = self.embedder.embed_document_batch(aux_texts) if aux_texts else []
        aux_lookup: dict[str, list[float] | None] = {t: e for t, e in zip(aux_texts, aux_embs)}

        self.graph.upsert_node(GraphNode(
            id=topic_id,
            node_type="topic",
            text=unit.domain,
            unit_id=None,
            embedding=aux_lookup.get(unit.domain),
        ))
        self.graph.add_edge(GraphEdge(topic_id, content_id, "contains"))

        tag_ids: list[str] = []
        for tag_text in tag_texts:
            tag_id = f"tag-{_slug(tag_text)}"
            if tag_id not in tag_ids:
                self.graph.upsert_node(GraphNode(
                    id=tag_id,
                    node_type="tag",
                    text=tag_text,
                    unit_id=None,
                    embedding=aux_lookup.get(tag_text),
                ))
                tag_ids.append(tag_id)
            self.graph.add_edge(GraphEdge(tag_id, content_id, "describes"))

        for cue_text in cue_texts:
            cue_id = f"cue-{_slug(cue_text)}-{unit.id[:8]}"
            self.graph.upsert_node(GraphNode(
                id=cue_id,
                node_type="cue",
                text=cue_text,
                unit_id=unit.id,
                embedding=aux_lookup.get(cue_text),
            ))
            for tag_id in tag_ids:
                self.graph.add_edge(GraphEdge(cue_id, tag_id, "activates"))
            self.graph.add_edge(GraphEdge(cue_id, content_id, "points_to"))

    def rebuild_all(self, units: list[ReasoningUnit]) -> None:
        for unit in units:
            self.incremental_update(unit)
