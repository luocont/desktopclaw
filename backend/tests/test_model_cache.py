"""Tests for embedding model cache completeness and resume detection."""

from __future__ import annotations

from pathlib import Path

from desktopclaw.agent.memory.model_cache import (
    has_resumable_partial,
    is_model_cache_complete,
)


def test_empty_cache_not_complete(tmp_path: Path) -> None:
    assert is_model_cache_complete(tmp_path, "Qwen/Qwen3-Embedding-0.6B") is False
    assert has_resumable_partial(tmp_path, "Qwen/Qwen3-Embedding-0.6B") is False


def test_metadata_only_is_partial_not_complete(tmp_path: Path) -> None:
    """Reproduces the bug: config files without weights must not count as cached."""
    root = tmp_path / "models--Qwen--Qwen3-Embedding-0.6B"
    snap = root / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    (snap / "config.json").write_text("{}", encoding="utf-8")
    (root / "blobs").mkdir()
    (root / "blobs" / "partial").write_bytes(b"x" * 100)

    assert is_model_cache_complete(tmp_path, "Qwen/Qwen3-Embedding-0.6B") is False
    assert has_resumable_partial(tmp_path, "Qwen/Qwen3-Embedding-0.6B") is True


def test_complete_when_weights_present(tmp_path: Path) -> None:
    root = tmp_path / "models--Qwen--Qwen3-Embedding-0.6B"
    snap = root / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    (snap / "model.safetensors").write_bytes(b"x" * 4096)

    assert is_model_cache_complete(tmp_path, "Qwen/Qwen3-Embedding-0.6B") is True
    assert has_resumable_partial(tmp_path, "Qwen/Qwen3-Embedding-0.6B") is False


def test_incomplete_blob_flagged_as_resumable(tmp_path: Path) -> None:
    root = tmp_path / "models--Qwen--Qwen3-Embedding-0.6B"
    blobs = root / "blobs"
    blobs.mkdir(parents=True)
    (blobs / "deadbeef.incomplete").write_bytes(b"partial")

    assert has_resumable_partial(tmp_path, "Qwen/Qwen3-Embedding-0.6B") is True
