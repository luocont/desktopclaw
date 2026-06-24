"""ReasoningBank JSON storage for agent strategy units."""

from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timezone
from pathlib import Path

from loguru import logger

from desktopclaw.agent.memory.types import ReasoningUnit


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors."""
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


class ReasoningBankStore:
    """CRUD for structured reasoning memory units."""

    MERGE_THRESHOLD = 0.92

    def __init__(self, bank_file: Path):
        self.bank_file = bank_file
        self._units: list[ReasoningUnit] | None = None

    def _load(self) -> list[ReasoningUnit]:
        if self._units is not None:
            return self._units
        if not self.bank_file.exists():
            self._units = []
            return self._units
        try:
            raw = json.loads(self.bank_file.read_text(encoding="utf-8"))
            self._units = [ReasoningUnit.from_dict(item) for item in raw]
        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Corrupt reasoning bank at {}, resetting", self.bank_file)
            self._units = []
        return self._units

    def _save(self) -> None:
        self.bank_file.parent.mkdir(parents=True, exist_ok=True)
        units = self._load()
        self.bank_file.write_text(
            json.dumps([u.to_dict() for u in units], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_units(self) -> list[ReasoningUnit]:
        return list(self._load())

    def get_by_id(self, unit_id: str) -> ReasoningUnit | None:
        for unit in self._load():
            if unit.id == unit_id:
                return unit
        return None

    def add_unit(self, unit: ReasoningUnit) -> ReasoningUnit:
        """Append or merge with an existing highly similar unit."""
        units = self._load()
        if unit.embedding:
            for existing in units:
                if existing.embedding and cosine_similarity(unit.embedding, existing.embedding) >= self.MERGE_THRESHOLD:
                    existing.confidence = max(existing.confidence, unit.confidence)
                    if unit.kind == "pitfall" and existing.kind == "strategy":
                        existing.kind = "pitfall"
                    self._save()
                    return existing
        if not unit.id:
            unit.id = str(uuid.uuid4())
        if not unit.created_at:
            unit.created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        units.append(unit)
        self._save()
        return unit

    def increment_hits(self, unit_ids: list[str]) -> None:
        id_set = set(unit_ids)
        for unit in self._load():
            if unit.id in id_set:
                unit.hit_count += 1
        self._save()

    def update_unit(self, unit: ReasoningUnit) -> None:
        """Replace an in-memory unit in place by id and persist."""
        units = self._load()
        for i, existing in enumerate(units):
            if existing.id == unit.id:
                units[i] = unit
                self._save()
                return

    def list_pending_units(self) -> list[ReasoningUnit]:
        """Units that still need (re)indexing by the background worker."""
        return [u for u in self._load() if u.index_status in ("pending", "failed")]

    def search_by_embedding(
        self,
        query_embedding: list[float] | None,
        top_k: int = 20,
    ) -> list[tuple[ReasoningUnit, float]]:
        """Return top-k *ready* units by cosine similarity.

        Only units with ``index_status == "ready"`` and a non-empty embedding
        participate — pending/failed units are invisible to vector search (they
        may surface via keyword fallback instead).
        """
        if not query_embedding:
            return []
        scored: list[tuple[ReasoningUnit, float]] = []
        for unit in self._load():
            if unit.index_status != "ready" or not unit.embedding:
                continue
            score = cosine_similarity(query_embedding, unit.embedding)
            scored.append((unit, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def search_by_keywords(self, query: str, top_k: int = 20) -> list[tuple[ReasoningUnit, float]]:
        """Fallback keyword search — includes pending and ready units."""
        query_lower = query.lower()
        tokens = [t for t in query_lower.split() if len(t) > 2]
        scored: list[tuple[ReasoningUnit, float]] = []
        for unit in self._load():
            text = unit.search_text().lower()
            score = 0.0
            if query_lower in unit.title.lower():
                score += 2.0
            for token in tokens:
                if token in text:
                    score += 1.0
            if score > 0:
                scored.append((unit, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]
