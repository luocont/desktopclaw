"""Tests for ReasoningBankStore."""

import json
from pathlib import Path

import pytest

from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore
from desktopclaw.agent.memory.types import ReasoningUnit


@pytest.fixture
def bank(tmp_path: Path) -> ReasoningBankStore:
    return ReasoningBankStore(tmp_path / "reasoning_bank.json")


def test_add_and_list_units(bank: ReasoningBankStore) -> None:
    unit = ReasoningUnit(
        id="u1",
        title="Use UTF-8 on Windows",
        description="When exec output is garbled",
        content="Set PYTHONIOENCODING=utf-8",
        kind="strategy",
        domain="shell",
        tools=["exec"],
        confidence=0.8,
        source="manual",
        created_at="2026-01-01T00:00:00Z",
    )
    bank.add_unit(unit)
    units = bank.list_units()
    assert len(units) == 1
    assert units[0].title == "Use UTF-8 on Windows"


def test_merge_similar_units(bank: ReasoningBankStore) -> None:
    emb = [1.0, 0.0, 0.0]
    u1 = ReasoningUnit(
        id="u1", title="A", description="d", content="c", embedding=emb,
        confidence=0.6, created_at="2026-01-01T00:00:00Z",
    )
    u2 = ReasoningUnit(
        id="u2", title="A copy", description="d", content="c", embedding=emb,
        confidence=0.9, created_at="2026-01-01T00:00:00Z",
    )
    bank.add_unit(u1)
    saved = bank.add_unit(u2)
    assert len(bank.list_units()) == 1
    assert saved.confidence == 0.9


def test_keyword_search(bank: ReasoningBankStore) -> None:
    bank.add_unit(ReasoningUnit(
        id="1", title="Windows encoding fix", description="exec errors",
        content="use utf-8", created_at="2026-01-01T00:00:00Z",
    ))
    results = bank.search_by_keywords("windows exec", top_k=5)
    assert len(results) == 1
    assert results[0][0].title == "Windows encoding fix"


def test_persists_to_json(tmp_path: Path) -> None:
    path = tmp_path / "reasoning_bank.json"
    bank = ReasoningBankStore(path)
    bank.add_unit(ReasoningUnit(
        id="x", title="T", description="D", content="C", created_at="2026-01-01T00:00:00Z",
    ))
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data[0]["title"] == "T"
