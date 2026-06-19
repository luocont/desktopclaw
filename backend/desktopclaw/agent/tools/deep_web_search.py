"""Deep iterative web research tool for the main agent."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from loguru import logger

from desktopclaw.agent.research.loop import ResearchLoop
from desktopclaw.agent.tools.base import Tool

ProgressCallback = Callable[[str], Awaitable[None]] | None


class DeepWebSearchTool(Tool):
    """Multi-round web research with cross-verified page reading."""

    name = "deep_web_search"
    description = (
        "Perform deep web research: iterative Bing searches, read 10-20 pages, "
        "cross-verify claims, and return a structured evidence-based report. "
        "Use for complex questions needing multiple sources and recency. "
        "Takes 1-2 minutes. Do NOT use for simple facts answerable from memory. "
        "Automated Bing access may violate Microsoft's terms of service."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Research question or topic to investigate",
            },
            "max_pages": {
                "type": "integer",
                "description": "Max pages to read deeply (10-20)",
                "minimum": 1,
                "maximum": 20,
            },
            "max_rounds": {
                "type": "integer",
                "description": "Max search rounds",
                "minimum": 1,
                "maximum": 10,
            },
        },
        "required": ["query"],
    }

    def __init__(self, research_loop: ResearchLoop):
        self._research_loop = research_loop
        self._progress_callback: ProgressCallback = None

    def set_progress_callback(self, callback: ProgressCallback) -> None:
        """Set callback for research progress updates (from AgentLoop on_progress)."""
        self._progress_callback = callback

    def set_research_context(
        self,
        main_model: str | None = None,
        fast_model: str | None = None,
    ) -> None:
        """Set per-request model overrides for the research pipeline."""
        self._research_loop.set_models(main_model=main_model, fast_model=fast_model)

    async def execute(
        self,
        query: str,
        max_pages: int | None = None,
        max_rounds: int | None = None,
        **kwargs: Any,
    ) -> str:
        query = (query or "").strip()
        if not query:
            return "Error: query is required"

        logger.info("DeepWebSearch: starting research for {!r}", query[:80])

        async def progress(msg: str) -> None:
            if self._progress_callback:
                await self._progress_callback(f"[research] {msg}")

        try:
            report = await self._research_loop.run(
                question=query,
                on_progress=progress,
                max_pages=max_pages,
                max_rounds=max_rounds,
            )
            header = (
                f"Research complete ({report.pages_read} pages, "
                f"{report.rounds_used} rounds, confidence: {report.confidence})\n\n"
            )
            return header + report.markdown
        except Exception as e:
            logger.error("DeepWebSearch failed: {}", e)
            return f"Error: deep web research failed — {e}"
