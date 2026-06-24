"""Tests for iterative deep web research."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from desktopclaw.agent.research.loop import ResearchLoop
from desktopclaw.agent.research.page_summarizer import PageSummarizer
from desktopclaw.agent.research.state import PageClaim, PageNote, ResearchState
from desktopclaw.agent.research.verifier import ResearchVerifier, claims_conflict, claims_similar
from desktopclaw.agent.tools.bing_search import SearchResult
from desktopclaw.agent.tools.deep_web_search import DeepWebSearchTool
from desktopclaw.config.schema import DeepResearchConfig
from desktopclaw.providers.base import LLMResponse


def test_claims_similar_and_conflict() -> None:
    assert claims_similar("LangGraph supports checkpoints", "langgraph supports checkpoints")
    assert claims_conflict("supports Redis", "does not support Redis")


def test_verifier_corroborated_two_domains() -> None:
    verifier = ResearchVerifier(provider=MagicMock(), model="test")
    state = ResearchState(question="test", pages_budget=10)
    notes = [
        PageNote(
            url="https://a.com/page1",
            claims=[PageClaim(text="Feature X exists", type="fact")],
        ),
        PageNote(
            url="https://b.org/page2",
            claims=[PageClaim(text="feature x exists", type="fact")],
        ),
    ]
    verifier.apply_rules(state, notes)
    assert len(state.known_facts) == 1
    assert state.known_facts[0].status == "corroborated"
    assert len(state.known_facts[0].domains) == 2


def test_verifier_single_source() -> None:
    verifier = ResearchVerifier(provider=MagicMock(), model="test")
    state = ResearchState(question="test", pages_budget=10)
    notes = [
        PageNote(
            url="https://only.com/post",
            claims=[PageClaim(text="Unique claim here", type="fact")],
        ),
    ]
    verifier.apply_rules(state, notes)
    assert state.known_facts[0].status == "single_source"
    assert state.open_questions


@pytest.mark.asyncio
async def test_page_summarizer_parses_llm_json() -> None:
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(
        return_value=LLMResponse(
            content=json.dumps({
                "title": "Test Page",
                "relevance": "high",
                "source_type": "blog",
                "claims": [{"text": "A fact", "type": "fact", "quote_hint": "fact"}],
                "summary": "Short summary",
            })
        )
    )
    fetch_tool = MagicMock()
    fetch_tool.execute = AsyncMock(
        return_value=json.dumps({"text": "Page body about LangGraph checkpoints and state."})
    )
    summarizer = PageSummarizer(provider=provider, model="test", fetch_tool=fetch_tool)
    note = await summarizer.summarize("https://example.com", "LangGraph state")
    assert note.title == "Test Page"
    assert len(note.claims) == 1
    assert note.claims[0].text == "A fact"


@pytest.mark.asyncio
async def test_research_loop_stops_within_max_rounds() -> None:
    config = DeepResearchConfig(max_pages=2, max_rounds=2, pages_per_round=1, serp_per_round=2)
    bing = MagicMock()
    bing.search = AsyncMock(
        return_value=[
            SearchResult(title="T1", url="https://a.com/1", snippet="s1"),
            SearchResult(title="T2", url="https://b.com/2", snippet="s2"),
        ]
    )
    provider = MagicMock()
    provider.chat_with_retry = AsyncMock(
        side_effect=[
            LLMResponse(content=json.dumps({"urls": ["https://a.com/1"]})),
            LLMResponse(content=json.dumps({
                "open_questions": [],
                "confidence": "high",
                "remove_open_questions": [],
                "disputed": [],
            })),
            LLMResponse(content="## 调研摘要\nDone."),
            LLMResponse(content=json.dumps({"urls": ["https://b.com/2"]})),
            LLMResponse(content=json.dumps({
                "open_questions": [],
                "confidence": "high",
                "remove_open_questions": [],
                "disputed": [],
            })),
            LLMResponse(content="## 调研摘要\nDone."),
        ]
    )
    loop = ResearchLoop(
        provider=provider,
        main_model="test",
        bing_backend=bing,
        web_proxy=None,
        config=config,
    )
    loop.page_summarizer.summarize = AsyncMock(
        side_effect=lambda url, question, on_progress=None: PageNote(
            url=url,
            title="T",
            claims=[PageClaim(text=f"claim from {url}", type="fact")],
            summary="s",
        )
    )

    report = await loop.run("test question", max_pages=2, max_rounds=2)
    assert report.pages_read <= 2
    assert report.rounds_used <= 2
    assert "调研摘要" in report.markdown or "Research" in report.markdown


@pytest.mark.asyncio
async def test_deep_web_search_tool_returns_report() -> None:
    research_loop = MagicMock()
    from desktopclaw.agent.research.state import ResearchReport

    research_loop.run = AsyncMock(
        return_value=ResearchReport(
            question="q",
            markdown="## 调研摘要\nResult",
            rounds_used=2,
            pages_read=3,
            confidence="medium",
        )
    )
    tool = DeepWebSearchTool(research_loop=research_loop)
    result = await tool.execute(query="test query")
    assert "Research complete" in result
    assert "调研摘要" in result
    research_loop.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_deep_web_search_progress_callback() -> None:
    research_loop = MagicMock()
    from desktopclaw.agent.research.state import ResearchReport

    async def fake_run(question, on_progress=None, max_pages=None, max_rounds=None,
                       sub_questions=None, constraints=None):
        if on_progress:
            await on_progress("test progress")
        return ResearchReport(question=question, markdown="ok")

    research_loop.run = fake_run
    tool = DeepWebSearchTool(research_loop=research_loop)
    progress_calls: list[str] = []

    async def capture(msg: str) -> None:
        progress_calls.append(msg)

    tool.set_progress_callback(capture)
    await tool.execute(query="q")
    assert any("test progress" in c for c in progress_calls)


def test_research_loop_dual_models() -> None:
    loop = ResearchLoop(
        provider=MagicMock(),
        main_model="main-model",
        fast_model="fast-model",
        bing_backend=MagicMock(),
        web_proxy=None,
        config=DeepResearchConfig(),
    )
    assert loop.page_summarizer.model == "fast-model"
    assert loop.verifier.model == "main-model"
    assert loop.model == "main-model"


def test_research_loop_fast_model_fallback() -> None:
    loop = ResearchLoop(
        provider=MagicMock(),
        main_model="main-only",
        fast_model="",
        bing_backend=MagicMock(),
        web_proxy=None,
        config=DeepResearchConfig(),
    )
    assert loop.page_summarizer.model == "main-only"
    assert loop.verifier.model == "main-only"


def test_research_loop_set_models() -> None:
    loop = ResearchLoop(
        provider=MagicMock(),
        main_model="main-a",
        fast_model="fast-a",
        bing_backend=MagicMock(),
        web_proxy=None,
        config=DeepResearchConfig(),
    )
    loop.set_models(main_model="main-b", fast_model="fast-b")
    assert loop.model == "main-b"
    assert loop.verifier.model == "main-b"
    assert loop.page_summarizer.model == "fast-b"


def test_deep_web_search_set_research_context() -> None:
    research_loop = MagicMock()
    tool = DeepWebSearchTool(research_loop=research_loop)
    tool.set_research_context(main_model="chat-model", fast_model="fast-model")
    research_loop.set_models.assert_called_once_with(
        main_model="chat-model", fast_model="fast-model"
    )
