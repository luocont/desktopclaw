"""Tests for embedding model migration (model/dim change → reindex)."""

import json
from pathlib import Path

import pytest

from desktopclaw.agent.memory.migration import migrate_embedding_model
from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore
from desktopclaw.agent.memory.types import ReasoningUnit


def _seed_raw(bank_file: Path, units: list[ReasoningUnit]) -> None:
    """Write units directly to JSON, bypassing add_unit's merge logic."""
    bank_file.parent.mkdir(parents=True, exist_ok=True)
    bank_file.write_text(
        json.dumps([u.to_dict() for u in units], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_model_change_marks_units_pending(tmp_path: Path) -> None:
    bank_file = tmp_path / "reasoning_bank.json"
    _seed_raw(bank_file, [
        ReasoningUnit(
            id="u1", title="T", description="d", content="c",
            embedding=[1.0] * 512, index_status="ready",
            embedding_model="all-MiniLM-L6-v2", embedding_dim=512,
            created_at="2026-01-01T00:00:00Z",
        ),
        ReasoningUnit(
            id="u2", title="T2", description="d", content="c",
            embedding=[1.0] * 512, index_status="ready",  # same model + dim → no reindex
            embedding_model="Qwen/Qwen3-Embedding-0.6B", embedding_dim=512,
            created_at="2026-01-01T00:00:00Z",
        ),
    ])
    n = migrate_embedding_model(tmp_path, "Qwen/Qwen3-Embedding-0.6B", current_dim=512)
    assert n == 1  # only u1 is stale

    bank = ReasoningBankStore(bank_file)
    u1 = bank.get_by_id("u1")
    u2 = bank.get_by_id("u2")
    assert u1.index_status == "pending"
    assert u1.embedding is None
    assert u1.embedding_model == ""
    assert u2.index_status == "ready"  # unchanged


def test_dim_change_marks_units_pending(tmp_path: Path) -> None:
    bank_file = tmp_path / "reasoning_bank.json"
    _seed_raw(bank_file, [
        ReasoningUnit(
            id="u1", title="T", description="d", content="c",
            embedding=[0.1] * 384, index_status="ready",
            embedding_model="Qwen/Qwen3-Embedding-0.6B", embedding_dim=384,
            created_at="2026-01-01T00:00:00Z",
        ),
    ])
    n = migrate_embedding_model(tmp_path, "Qwen/Qwen3-Embedding-0.6B", current_dim=512)
    assert n == 1
    bank = ReasoningBankStore(bank_file)
    u1 = bank.get_by_id("u1")
    assert u1.index_status == "pending"
    assert u1.embedding_dim == 0


def test_no_change_no_migration(tmp_path: Path) -> None:
    bank_file = tmp_path / "reasoning_bank.json"
    _seed_raw(bank_file, [
        ReasoningUnit(
            id="u1", title="T", description="d", content="c",
            embedding=[0.1] * 512, index_status="ready",
            embedding_model="Qwen/Qwen3-Embedding-0.6B", embedding_dim=512,
            created_at="2026-01-01T00:00:00Z",
        ),
    ])
    n = migrate_embedding_model(tmp_path, "Qwen/Qwen3-Embedding-0.6B", current_dim=512)
    assert n == 0
    bank = ReasoningBankStore(bank_file)
    assert bank.get_by_id("u1").index_status == "ready"


def test_empty_bank_returns_zero(tmp_path: Path) -> None:
    bank_file = tmp_path / "reasoning_bank.json"
    bank_file.write_text("[]", encoding="utf-8")
    n = migrate_embedding_model(tmp_path, "Qwen/Qwen3-Embedding-0.6B", current_dim=512)
    assert n == 0


def test_legacy_units_without_embedding_model_left_alone(tmp_path: Path) -> None:
    """Units with empty embedding_model (legacy/never-indexed) are not touched by migration.

    They are already 'pending' and will be picked up by recover_pending instead.
    """
    bank_file = tmp_path / "reasoning_bank.json"
    _seed_raw(bank_file, [
        ReasoningUnit(
            id="u1", title="T", description="d", content="c",
            embedding=None, index_status="pending",
            embedding_model="", embedding_dim=0,
            created_at="2026-01-01T00:00:00Z",
        ),
    ])
    n = migrate_embedding_model(tmp_path, "Qwen/Qwen3-Embedding-0.6B", current_dim=512)
    assert n == 0
