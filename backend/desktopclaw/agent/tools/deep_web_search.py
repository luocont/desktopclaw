"""Deep iterative web research tool for the main agent."""

from __future__ import annotations

from typing import Any, Awaitable, Callable

from loguru import logger

from desktopclaw.agent.research.loop import ResearchLoop
from desktopclaw.agent.tools.base import Tool
from desktopclaw.utils.usage import get_tracker

ProgressCallback = Callable[[str], Awaitable[None]] | None


class DeepWebSearchTool(Tool):
    """Multi-round web research with cross-verified page reading."""

    name = "deep_web_search"
    description = (
        "Dispatch a research task to the web-search agent: iterative Bing searches, "
        "read 10-20 pages, cross-verify claims, return a structured evidence-based report. "
        "BEFORE calling, YOU (the main agent) must analyze the user's real intent and "
        "decompose it into a focused brief: a refined `query` (the core research question, "
        "not the user's raw words), specific `sub_questions` to investigate, and any "
        "`constraints` (recency, region, language, source preferences, scope limits). "
        "A well-formed brief makes the search agent far more effective. "
        "Use for complex questions needing multiple sources and recency. Takes 1-2 minutes. "
        "Do NOT use for simple facts answerable from memory. "
        "Automated Bing access may violate Microsoft's terms of service."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The refined core research question to dispatch to the search agent. "
                    "Rephrase the user's intent into a clear, self-contained question — "
                    "do NOT just copy the user's raw message."
                ),
            },
            "sub_questions": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Specific sub-questions the research must answer, derived from your "
                    "analysis of the user's need. These seed the search agent's planning."
                ),
            },
            "constraints": {
                "type": "string",
                "description": (
                    "Optional constraints from your analysis: time/recency window, region, "
                    "language, preferred/authoritative sources, or scope limits."
                ),
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
        sub_questions: list[str] | None = None,
        constraints: str | None = None,
        **kwargs: Any,
    ) -> str:
        query = (query or "").strip()
        if not query:
            return "Error: query is required"

        logger.info(
            "DeepWebSearch: dispatching research for {!r} ({} sub-questions)",
            query[:80], len(sub_questions or []),
        )

        async def progress(msg: str) -> None:
            if self._progress_callback:
                await self._progress_callback(f"[research] {msg}")

        tracker = get_tracker()
        prev_source = tracker.current_source if tracker else "main"
        if tracker:
            tracker.current_source = "research"
        try:
            report = await self._research_loop.run(
                question=query,
                on_progress=progress,
                max_pages=max_pages,
                max_rounds=max_rounds,
                sub_questions=sub_questions,
                constraints=constraints,
            )
            header = (
                f"Research complete ({report.pages_read} pages, "
                f"{report.rounds_used} rounds, confidence: {report.confidence})\n\n"
            )
            return header + report.markdown
        except Exception as e:
            logger.error("DeepWebSearch failed: {}", e)
            return f"Error: deep web research failed — {e}"
        finally:
            if tracker:
                tracker.current_source = prev_source
