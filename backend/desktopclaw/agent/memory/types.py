"""Data types for the agent memory system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

NodeType = Literal["cue", "tag", "content", "topic"]
UnitKind = Literal["strategy", "pitfall"]
UnitSource = Literal["distilled", "manual"]
TaskOutcome = Literal["success", "partial", "failure"]
TriggerLevel = Literal["L1", "L2", "L3"]
IndexStatus = Literal["pending", "ready", "failed"]


@dataclass
class ReasoningUnit:
    """Structured reasoning memory unit (ReasoningBank-style).

    Indexing lifecycle:
      pending → ready (async IndexWorker finished embed + graph)
      pending → failed (max retries exhausted; keyword fallback still works)
    """

    id: str
    title: str
    description: str
    content: str
    kind: UnitKind = "strategy"
    domain: str = "general"
    tools: list[str] = field(default_factory=list)
    confidence: float = 0.7
    source: UnitSource = "distilled"
    created_at: str = ""
    hit_count: int = 0
    embedding: list[float] | None = None
    # Indexing metadata — defaults make old data load as "pending" so the
    # async IndexWorker can (re)build embeddings/vector state in the background.
    index_status: IndexStatus = "pending"
    index_error: str = ""
    index_attempts: int = 0
    embedding_model: str = ""  # model used when the embedding was computed
    embedding_dim: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "kind": self.kind,
            "domain": self.domain,
            "tools": self.tools,
            "confidence": self.confidence,
            "source": self.source,
            "created_at": self.created_at,
            "hit_count": self.hit_count,
            "embedding": self.embedding,
            "index_status": self.index_status,
            "index_error": self.index_error,
            "index_attempts": self.index_attempts,
            "embedding_model": self.embedding_model,
            "embedding_dim": self.embedding_dim,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReasoningUnit:
        return cls(
            id=str(data["id"]),
            title=str(data.get("title", "")),
            description=str(data.get("description", "")),
            content=str(data.get("content", "")),
            kind=data.get("kind", "strategy"),
            domain=str(data.get("domain", "general")),
            tools=list(data.get("tools") or []),
            confidence=float(data.get("confidence", 0.7)),
            source=data.get("source", "distilled"),
            created_at=str(data.get("created_at", "")),
            hit_count=int(data.get("hit_count", 0)),
            embedding=data.get("embedding"),
            # Backwards compat: legacy records have no index_status. If they
            # already carry an embedding, treat them as ready; otherwise pending
            # so the IndexWorker rebuilds them.
            index_status=data.get("index_status", "ready" if data.get("embedding") else "pending"),
            index_error=str(data.get("index_error", "")),
            index_attempts=int(data.get("index_attempts", 0)),
            embedding_model=str(data.get("embedding_model", "")),
            embedding_dim=int(data.get("embedding_dim", 0)),
        )

    def search_text(self) -> str:
        """Combined text for embedding and keyword fallback."""
        tools = ", ".join(self.tools)
        return f"{self.title}\n{self.description}\n{self.content}\n{self.domain}\n{tools}"


@dataclass
class GraphNode:
    """Node in the MRAgent Cue-Tag-Content graph."""

    id: str
    node_type: NodeType
    text: str
    unit_id: str | None = None
    embedding: list[float] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type,
            "text": self.text,
            "unit_id": self.unit_id,
            "embedding": self.embedding,
        }


@dataclass
class GraphEdge:
    """Directed edge between graph nodes."""

    src_id: str
    dst_id: str
    relation: str = "links"


@dataclass
class RetrievalResult:
    """Output of a memory retrieval pass."""

    units: list[ReasoningUnit]
    trigger_level: TriggerLevel
    query: str
