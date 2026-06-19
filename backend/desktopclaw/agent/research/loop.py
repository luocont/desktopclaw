"""Iterative research loop: plan, search, read, verify, synthesize."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Awaitable, Callable

from loguru import logger

from desktopclaw.agent.research.page_summarizer import PageSummarizer
from desktopclaw.agent.research.state import Confidence, PageNote, ResearchReport, ResearchState
from desktopclaw.agent.research.verifier import ResearchVerifier, _parse_json
from desktopclaw.agent.tools.bing_search import BingSearchBackend, SearchResult
from desktopclaw.agent.tools.web import WebFetchTool
from desktopclaw.config.schema import DeepResearchConfig
from desktopclaw.providers.base import LLMProvider

ProgressCallback = Callable[[str], Awaitable[None]] | None


class ResearchLoop:
    """Orchestrates multi-round web research with cross-verification."""

    def __init__(
        self,
        provider: LLMProvider,
        main_model: str,
        bing_backend: BingSearchBackend,
        web_proxy: str | None,
        config: DeepResearchConfig,
        fast_model: str | None = None,
    ):
        self.provider = provider
        self._main_model = main_model
        self._fast_model = fast_model or main_model
        self.model = self._main_model
        self.bing_backend = bing_backend
        self.config = config
        fetch_tool = WebFetchTool(max_chars=config.fetch_max_chars, proxy=web_proxy)
        semaphore = asyncio.Semaphore(config.fetch_concurrency)
        self.page_summarizer = PageSummarizer(
            provider=provider,
            model=self._fast_model,
            fetch_tool=fetch_tool,
            page_timeout_s=config.page_timeout_s,
            semaphore=semaphore,
        )
        self.verifier = ResearchVerifier(provider=provider, model=self._main_model)

    def set_models(self, main_model: str | None = None, fast_model: str | None = None) -> None:
        """Update models at runtime (e.g. per-chat main model override)."""
        if main_model:
            self._main_model = main_model
            self.model = main_model
            self.verifier.model = main_model
        if fast_model:
            self._fast_model = fast_model
            self.page_summarizer.model = fast_model

    async def run(
        self,
        question: str,
        on_progress: ProgressCallback = None,
        max_pages: int | None = None,
        max_rounds: int | None = None,
    ) -> ResearchReport:
        cfg = self.config
        pages_cap = min(max(max_pages or cfg.max_pages, 1), 20)
        rounds_cap = min(max(max_rounds or cfg.max_rounds, 1), 10)

        state = ResearchState(
            question=question,
            pages_budget=pages_cap,
            max_pages=pages_cap,
        )

        async def progress(msg: str) -> None:
            if on_progress:
                await on_progress(msg)

        async def _run() -> ResearchReport:
            no_progress_rounds = 0
            while state.round < rounds_cap and state.pages_budget > 0:
                state.round += 1
                await progress(f"Round {state.round}/{rounds_cap}: planning search…")

                query = await self._plan_search_query(state)
                if not query:
                    query = state.question

                if query in state.searched_queries:
                    alt = await self._plan_search_query(state, force_different=True)
                    if alt and alt not in state.searched_queries:
                        query = alt
                    else:
                        logger.info("ResearchLoop: no new query, stopping")
                        break

                state.searched_queries.append(query)
                await progress(f"Round {state.round}: searching «{query[:50]}»…")

                try:
                    serp = await self.bing_backend.search(query, cfg.serp_per_round)
                except Exception as e:
                    err_msg = str(e) or f"{type(e).__name__}"
                    logger.error("ResearchLoop search failed: {}", err_msg)
                    if state.round == 1:
                        return ResearchReport(
                            question=question,
                            markdown=f"## 调研失败\n\nBing 搜索失败：{err_msg}",
                            rounds_used=state.round,
                            pages_read=len(state.read_urls),
                            confidence=state.confidence,
                        )
                    break

                candidates = self._filter_serp(serp, state)
                if not candidates:
                    no_progress_rounds += 1
                    if no_progress_rounds >= 2:
                        break
                    continue

                pick_count = min(cfg.pages_per_round, state.pages_budget, len(candidates))
                urls = await self._pick_urls(state, candidates, pick_count)
                if not urls:
                    urls = [c.url for c in candidates[:pick_count]]

                urls = [u for u in urls if u not in state.read_urls][:pick_count]
                if not urls:
                    no_progress_rounds += 1
                    if no_progress_rounds >= 2:
                        break
                    continue

                await progress(
                    f"Round {state.round}: reading {len(urls)} page(s) "
                    f"({len(state.read_urls)}/{state.max_pages} total)…"
                )

                round_notes = await self._read_pages(urls, state.question, progress)
                for url in urls:
                    state.read_urls.add(url)
                state.pages_budget = max(0, state.pages_budget - len(urls))
                state.page_notes.extend(round_notes)

                await progress(f"Round {state.round}: verifying claims…")
                facts_before = len(state.known_facts)
                await self.verifier.verify_and_update(state, round_notes)

                new_facts = len(state.known_facts) - facts_before
                if new_facts == 0 and state.last_round_new_facts == 0:
                    no_progress_rounds += 1
                else:
                    no_progress_rounds = 0

                if self._should_stop(state, cfg):
                    break
                if no_progress_rounds >= 2:
                    break

            await progress("Synthesizing final report…")
            markdown = await self._synthesize_report(state)
            return ResearchReport(
                question=question,
                markdown=markdown,
                rounds_used=state.round,
                pages_read=len(state.read_urls),
                confidence=state.confidence,
                source_urls=list(state.read_urls),
            )

        try:
            return await asyncio.wait_for(_run(), timeout=cfg.total_timeout_s)
        except asyncio.TimeoutError:
            return ResearchReport(
                question=question,
                markdown=(
                    f"Research timed out after {cfg.total_timeout_s}s. "
                    f"Partial: {state.snapshot_for_llm()}"
                ),
                rounds_used=state.round,
                pages_read=len(state.read_urls),
                confidence=state.confidence,
                source_urls=list(state.read_urls),
            )

    def _should_stop(self, state: ResearchState, cfg: DeepResearchConfig) -> bool:
        if state.pages_budget <= 0:
            return True
        if state.confidence == "high" and not state.open_questions:
            return True
        if state.confidence == cfg.min_confidence_to_stop and not state.open_questions:
            return True
        return False

    async def _plan_search_query(
        self,
        state: ResearchState,
        force_different: bool = False,
    ) -> str:
        if state.round == 1 and not force_different:
            return state.question

        extra = (
            "You MUST propose a query different from all previous searches."
            if force_different
            else ""
        )
        prompt = f"""Plan the next web search query for this research.

{state.snapshot_for_llm()}

Previous queries (do not repeat): {state.searched_queries}
{extra}

Respond with JSON only: {{"search_query": "..."}}"""

        try:
            response = await self.provider.chat_with_retry(
                messages=[
                    {"role": "system", "content": "You plan web searches. JSON only."},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                model=self.model,
                temperature=0.3,
                max_tokens=256,
            )
            data = _parse_json(response.content or "")
            if data and isinstance(data.get("search_query"), str):
                return data["search_query"].strip()
        except Exception as e:
            logger.warning("Plan search query failed: {}", e)

        if state.open_questions:
            return state.open_questions[0][:100]
        return state.question

    async def _pick_urls(
        self,
        state: ResearchState,
        candidates: list[SearchResult],
        count: int,
    ) -> list[str]:
        serp_lines = "\n".join(
            f"{i}. {r.title} | {r.url} | {r.snippet[:120]}"
            for i, r in enumerate(candidates, 1)
        )
        prompt = f"""Select up to {count} URLs to read deeply for this research.

Question: {state.question}
Already read: {list(state.read_urls)}

Search results:
{serp_lines}

Prefer high relevance, diverse domains, official sources when possible.
Respond JSON only: {{"urls": ["https://...", ...]}}"""

        try:
            response = await self.provider.chat_with_retry(
                messages=[
                    {"role": "system", "content": "You select URLs for research. JSON only."},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                model=self.model,
                temperature=0.2,
                max_tokens=512,
            )
            data = _parse_json(response.content or "")
            urls = data.get("urls", []) if data else []
            valid = [u for u in urls if isinstance(u, str) and u.startswith("http")]
            return valid[:count]
        except Exception as e:
            logger.warning("Pick URLs failed: {}", e)
            return []

    async def _read_pages(
        self,
        urls: list[str],
        question: str,
        on_progress: ProgressCallback,
    ) -> list[PageNote]:
        tasks = [
            self.page_summarizer.summarize(url, question, on_progress=on_progress)
            for url in urls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        notes: list[PageNote] = []
        for url, result in zip(urls, results):
            if isinstance(result, Exception):
                notes.append(PageNote(url=url, error=str(result)))
            else:
                notes.append(result)
        return notes

    def _filter_serp(
        self,
        serp: list[SearchResult],
        state: ResearchState,
    ) -> list[SearchResult]:
        out: list[SearchResult] = []
        for r in serp:
            if r.url in state.read_urls:
                continue
            if not r.url.startswith("http"):
                continue
            out.append(r)
        return out

    async def _synthesize_report(self, state: ResearchState) -> str:
        corroborated = [c for c in state.known_facts if c.status == "corroborated"]
        single = [c for c in state.known_facts if c.status == "single_source"]
        disputed = state.disputed_claims or [c for c in state.known_facts if c.status == "conflicting"]

        facts_block = state.snapshot_for_llm()
        sources = "\n".join(
            f"- {n.title or n.url}: {n.url}" for n in state.page_notes if not n.error
        )[:3000]

        prompt = f"""Write a research report in Markdown for the main agent.

Research question: {state.question}
Confidence: {state.confidence}
Pages read: {len(state.read_urls)}
Rounds: {state.round}

State:
{facts_block}

Sources read:
{sources}

Structure the report EXACTLY with these sections (use Chinese if the question is Chinese):

## 调研摘要
(800-1200 characters, synthesized answer)

## 高置信结论
(multi-source corroborated facts, with brief source attribution)

## 单源或未充分验证
(single-source facts, note limitation)

## 存在争议或未核实
(disputed or unresolved items)

## 来源列表
(numbered URLs with one-line relevance)

Keep total length under 3500 characters. Do not invent facts beyond the state."""

        try:
            response = await self.provider.chat_with_retry(
                messages=[
                    {"role": "system", "content": "You write evidence-based research reports."},
                    {"role": "user", "content": prompt},
                ],
                tools=None,
                model=self.model,
                temperature=0.4,
                max_tokens=4096,
            )
            text = (response.content or "").strip()
            if text:
                return text[:4000]
        except Exception as e:
            logger.error("Synthesize report failed: {}", e)

        return self._fallback_report(state, corroborated, single, disputed)

    def _fallback_report(
        self,
        state: ResearchState,
        corroborated: list,
        single: list,
        disputed: list,
    ) -> str:
        lines = [
            f"# Research: {state.question}",
            f"\nConfidence: {state.confidence} | Pages: {len(state.read_urls)} | Rounds: {state.round}",
            "\n## 高置信结论",
        ]
        for c in corroborated[:15]:
            lines.append(f"- {c.text} (sources: {len(c.domains)} domains)")
        lines.append("\n## 单源或未充分验证")
        for c in single[:10]:
            lines.append(f"- {c.text}")
        if disputed:
            lines.append("\n## 存在争议")
            for c in disputed[:10]:
                lines.append(f"- {c.text}")
        lines.append("\n## 来源列表")
        for i, url in enumerate(state.read_urls, 1):
            lines.append(f"{i}. {url}")
        return "\n".join(lines)[:4000]
