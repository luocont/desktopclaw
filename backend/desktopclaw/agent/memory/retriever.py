"""MRAgent-style active memory retrieval."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from loguru import logger

from desktopclaw.agent.memory import injector
from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore, cosine_similarity
from desktopclaw.agent.memory.types import ReasoningUnit, RetrievalResult, TriggerLevel
from desktopclaw.config.schema import MemoryConfig

if TYPE_CHECKING:
    from desktopclaw.agent.memory.embedder import LocalEmbedder
    from desktopclaw.agent.memory.graph import MemoryGraphStore
    from desktopclaw.providers.base import LLMProvider

_ROUTE_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "memory_route",
            "description": "Choose the next memory graph traversal action.",
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["forward_expand", "backward_trace", "stop"],
                    },
                    "node_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Active node IDs to expand from",
                    },
                    "sufficient": {
                        "type": "boolean",
                        "description": "Whether accumulated evidence is enough",
                    },
                },
                "required": ["action", "node_ids", "sufficient"],
            },
        },
    }
]


def _extract_cues_from_query(query: str) -> list[str]:
    parts = re.split(r"[\s,;/|]+", query.strip())
    return [p for p in parts if len(p) > 2][:10]


class MRAgentRetriever:
    """Active iterative retrieval over reasoning bank + memory graph."""

    def __init__(
        self,
        embedder: LocalEmbedder,
        bank: ReasoningBankStore,
        graph: MemoryGraphStore,
        provider: LLMProvider,
        model: str,
        fast_model: str,
        config: MemoryConfig,
    ):
        self.embedder = embedder
        self.bank = bank
        self.graph = graph
        self.provider = provider
        self.model = model
        self.fast_model = fast_model or model
        self.config = config
        self._session_cache: dict[str, list[ReasoningUnit]] = {}

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    async def retrieve(
        self,
        query: str,
        level: TriggerLevel,
        session_key: str | None = None,
    ) -> RetrievalResult:
        if not self.enabled or not query.strip():
            return RetrievalResult(units=[], trigger_level=level, query=query)

        cache_key = f"{session_key}:{level}:{query[:200]}" if session_key else ""
        if cache_key and cache_key in self._session_cache:
            cached = self._session_cache[cache_key]
            return RetrievalResult(units=cached, trigger_level=level, query=query)

        if level == "L1":
            units = await self._retrieve_l1(query)
        else:
            max_iter = 2 if level == "L2" else self.config.mragent_max_iterations
            units = await self._retrieve_active(query, max_iter)

        top_k = self.config.retrieval_top_k
        units = units[:top_k]
        if units:
            self.bank.increment_hits([u.id for u in units])
        if cache_key:
            self._session_cache[cache_key] = units

        return RetrievalResult(units=units, trigger_level=level, query=query)

    async def _retrieve_l1(self, query: str) -> list[ReasoningUnit]:
        """Vector search (ready units) + keyword fallback (incl. pending units).

        Query embedding is async with a timeout — on expiry or model failure we
        fall back to pure keyword search so the user-facing turn never blocks.
        Pending units (not yet indexed) surface via keywords only.
        """
        embedding = await self.embedder.embed_query_async(query)
        seen: set[str] = set()
        merged: list[ReasoningUnit] = []
        top_k = self.config.retrieval_top_k
        if embedding:
            for unit, _ in self.bank.search_by_embedding(embedding, top_k=top_k):
                if unit.id not in seen:
                    seen.add(unit.id)
                    merged.append(unit)
        # Keyword fallback fills gaps (pending units invisible to vector search)
        # and fully covers the case when no embedding was produced.
        for unit, _ in self.bank.search_by_keywords(query, top_k=top_k):
            if unit.id not in seen:
                seen.add(unit.id)
                merged.append(unit)
        return merged[:top_k]

    async def _retrieve_active(self, query: str, max_iterations: int) -> list[ReasoningUnit]:
        """Multi-round graph traversal with optional LLM routing."""
        l1_units = await self._retrieve_l1(query)
        unit_ids = {u.id for u in l1_units}

        cues = _extract_cues_from_query(query)
        active_node_ids: list[str] = []
        for cue in cues:
            for node in self.graph.find_nodes_by_text_contains(cue, "cue"):
                active_node_ids.append(node.id)
                if node.unit_id:
                    unit_ids.add(node.unit_id)

        # Embed the query once and reuse across all content nodes — previously
        # this re-embedded per node, which was both slow and racy.
        q_emb = await self.embedder.embed_query_async(query)
        if q_emb:
            for content in self.graph.list_content_nodes():
                if content.unit_id and content.embedding:
                    if cosine_similarity(q_emb, content.embedding) > 0.5:
                        unit_ids.add(content.unit_id)
                        active_node_ids.append(content.id)

        accumulated_ids = set(unit_ids)
        for _ in range(max_iterations):
            if not active_node_ids:
                break
            route = await self._llm_route(query, active_node_ids, list(accumulated_ids))
            if route.get("sufficient") or route.get("action") == "stop":
                break
            action = route.get("action", "forward_expand")
            expand_ids = route.get("node_ids") or active_node_ids
            new_nodes: list[str] = []
            for nid in expand_ids[:5]:
                direction = "out" if action == "forward_expand" else "in"
                for neighbor in self.graph.get_neighbors(nid, direction):
                    new_nodes.append(neighbor.id)
                    if neighbor.unit_id:
                        accumulated_ids.add(neighbor.unit_id)
            active_node_ids = new_nodes[:10]
            if not new_nodes:
                break

        units: list[ReasoningUnit] = []
        for uid in accumulated_ids:
            unit = self.bank.get_by_id(uid)
            if unit:
                units.append(unit)
        units.sort(key=lambda u: u.confidence, reverse=True)
        if not units:
            return l1_units
        return units

    async def _llm_route(
        self,
        query: str,
        active_node_ids: list[str],
        unit_ids: list[str],
    ) -> dict[str, Any]:
        node_summaries = []
        for nid in active_node_ids[:8]:
            node = self.graph.get_node(nid)
            if node:
                node_summaries.append(f"{node.id} ({node.node_type}): {node.text[:120]}")
        unit_summaries = []
        for uid in unit_ids[:5]:
            unit = self.bank.get_by_id(uid)
            if unit:
                unit_summaries.append(f"{unit.id}: {unit.title}")

        prompt = f"""Query: {query}

Active nodes:
{chr(10).join(node_summaries) or 'none'}

Accumulated units:
{chr(10).join(unit_summaries) or 'none'}

Choose next traversal action or stop if evidence is sufficient."""

        try:
            response = await self.provider.chat_with_retry(
                messages=[
                    {"role": "system", "content": "You route memory graph traversal. Call memory_route."},
                    {"role": "user", "content": prompt},
                ],
                tools=_ROUTE_TOOL,
                model=self.fast_model,
                temperature=0,
                max_tokens=512,
                tool_choice="auto",
            )
            if response.has_tool_calls:
                args = response.tool_calls[0].arguments
                if isinstance(args, str):
                    args = json.loads(args)
                return args if isinstance(args, dict) else {}
        except Exception:
            logger.debug("LLM memory routing failed, using heuristic expand")
        return {"action": "forward_expand", "node_ids": active_node_ids, "sufficient": False}

    async def retrieve_for_task(self, task: str, session_key: str | None = None) -> str:
        """L1 retrieval formatted for system prompt injection."""
        result = await self.retrieve(task, "L1", session_key=session_key)
        return injector.format_strategies(result.units)

    async def retrieve_and_inject(
        self,
        messages: list[dict],
        level: TriggerLevel,
        session_key: str | None = None,
    ) -> list[dict]:
        from desktopclaw.agent.memory.triggers import extract_query_from_messages

        query = extract_query_from_messages(messages)
        if not query:
            return messages
        result = await self.retrieve(query, level, session_key=session_key)
        if not result.units:
            return messages
        return injector.inject_before_llm(messages, result.units)
