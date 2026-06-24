"""Tests for the deep_web_search brief contract (main agent analysis → search agent)."""

import pytest

from desktopclaw.agent.research.state import ResearchReport, ResearchState
from desktopclaw.agent.tools.deep_web_search import DeepWebSearchTool


class _FakeResearchLoop:
    """Records the kwargs passed to run() and returns a canned report."""

    def __init__(self) -> None:
        self.last_kwargs: dict = {}

    def set_models(self, **kwargs):  # noqa: D401 - test stub
        pass

    async def run(self, question, on_progress=None, max_pages=None,
                  max_rounds=None, sub_questions=None, constraints=None):
        self.last_kwargs = {
            "question": question,
            "sub_questions": sub_questions,
            "constraints": constraints,
            "max_pages": max_pages,
            "max_rounds": max_rounds,
        }
        return ResearchReport(question=question, markdown="ok", confidence="high")


@pytest.mark.asyncio
async def test_deep_search_forwards_brief_to_search_agent() -> None:
    fake = _FakeResearchLoop()
    tool = DeepWebSearchTool(research_loop=fake)  # type: ignore[arg-type]

    result = await tool.execute(
        query="What is the latest stable Python release?",
        sub_questions=["release date", "key features"],
        constraints="recency: last 6 months; official python.org sources",
    )

    assert "Research complete" in result
    assert fake.last_kwargs["question"] == "What is the latest stable Python release?"
    assert fake.last_kwargs["sub_questions"] == ["release date", "key features"]
    assert "recency" in fake.last_kwargs["constraints"]


@pytest.mark.asyncio
async def test_deep_search_requires_query() -> None:
    fake = _FakeResearchLoop()
    tool = DeepWebSearchTool(research_loop=fake)  # type: ignore[arg-type]
    result = await tool.execute(query="   ")
    assert result == "Error: query is required"


def test_research_state_seeds_open_questions_and_constraints() -> None:
    state = ResearchState(
        question="q",
        open_questions=["sub1", "sub2"],
        constraints="recent only",
    )
    snapshot = state.snapshot_for_llm()
    assert "sub1" in snapshot
    assert "Constraints: recent only" in snapshot
