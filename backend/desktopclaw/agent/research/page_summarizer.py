"""Per-page fetch and LLM summarization worker."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Awaitable, Callable

from loguru import logger

from desktopclaw.agent.research.state import PageClaim, PageNote, Relevance, SourceType
from desktopclaw.agent.tools.web import WebFetchTool
from desktopclaw.providers.base import LLMProvider

ProgressCallback = Callable[[str], Awaitable[None]] | None


class PageSummarizer:
    """Fetch a single URL and extract structured claims via one LLM call."""

    def __init__(
        self,
        provider: LLMProvider,
        model: str,
        fetch_tool: WebFetchTool,
        page_timeout_s: int = 20,
        semaphore: asyncio.Semaphore | None = None,
    ):
        self.provider = provider
        self.model = model
        self.fetch_tool = fetch_tool
        self.page_timeout_s = page_timeout_s
        self.semaphore = semaphore or asyncio.Semaphore(3)

    async def summarize(
        self,
        url: str,
        research_question: str,
        on_progress: ProgressCallback = None,
    ) -> PageNote:
        async with self.semaphore:
            if on_progress:
                await on_progress(f"Reading page: {url[:60]}…")
            try:
                return await asyncio.wait_for(
                    self._summarize_once(url, research_question),
                    timeout=self.page_timeout_s,
                )
            except asyncio.TimeoutError:
                return PageNote(url=url, error=f"Page timeout after {self.page_timeout_s}s")
            except Exception as e:
                logger.warning("PageSummarizer failed for {}: {}", url, e)
                return PageNote(url=url, error=str(e))

    async def _summarize_once(self, url: str, research_question: str) -> PageNote:
        raw = await self.fetch_tool.execute(url=url, extractMode="text", maxChars=8000)
        page_text = _extract_fetch_text(raw)
        if not page_text:
            return PageNote(url=url, error="Empty or failed fetch")

        prompt = f"""Research question: {research_question}

Page URL: {url}

Page content (truncated):
{page_text[:6000]}

Extract information relevant to the research question. Respond with JSON only:
{{
  "title": "page title",
  "relevance": "high|medium|low",
  "source_type": "official|blog|news|forum|unknown",
  "claims": [
    {{"text": "specific claim", "type": "fact|opinion|procedure", "quote_hint": "short phrase from text"}}
  ],
  "summary": "≤200 characters in Chinese or English matching the question"
}}

Only include claims directly relevant to the research question. Max 5 claims."""

        response = await self.provider.chat_with_retry(
            messages=[
                {"role": "system", "content": "You extract structured research notes. JSON only."},
                {"role": "user", "content": prompt},
            ],
            tools=None,
            model=self.model,
            temperature=0.2,
            max_tokens=1024,
        )

        data = _parse_json(response.content or "")
        if not data:
            return PageNote(url=url, error="Failed to parse summarizer JSON", summary=page_text[:200])

        claims: list[PageClaim] = []
        for item in data.get("claims", [])[:5]:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            ctype = item.get("type", "fact")
            if ctype not in ("fact", "opinion", "procedure"):
                ctype = "fact"
            claims.append(
                PageClaim(
                    text=text,
                    type=ctype,
                    quote_hint=str(item.get("quote_hint", "")),
                )
            )

        relevance: Relevance = data.get("relevance", "medium")
        if relevance not in ("high", "medium", "low"):
            relevance = "medium"

        source_type: SourceType = data.get("source_type", "unknown")
        if source_type not in ("official", "blog", "news", "forum", "unknown"):
            source_type = "unknown"

        return PageNote(
            url=url,
            title=str(data.get("title", "")),
            relevance=relevance,
            source_type=source_type,
            claims=claims,
            summary=str(data.get("summary", ""))[:300],
        )


def _extract_fetch_text(raw: str) -> str:
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            if data.get("error"):
                return ""
            return str(data.get("text", ""))
    except json.JSONDecodeError:
        pass
    return raw


def _parse_json(text: str) -> dict | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import json_repair

            return json_repair.loads(text)
        except Exception:
            return None
