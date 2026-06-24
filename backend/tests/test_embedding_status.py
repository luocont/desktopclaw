"""Tests for embedding model load status tracking."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from desktopclaw.agent.memory.embedder import LocalEmbedder
from desktopclaw.agent.memory.embedding_status import EmbeddingLoadTracker
from desktopclaw.api.memory_helpers import build_memory_payload, embedding_model_for_ui
from desktopclaw.config.schema import MemoryConfig


def test_tracker_download_progress() -> None:
    tracker = EmbeddingLoadTracker("Qwen/Qwen3-Embedding-0.6B")
    tracker.set_downloading(42.5)
    snap = tracker.snapshot()
    assert snap["status"] == "downloading"
    assert snap["progress"] == 42.5
    assert "42" in snap["message"]


def test_tracker_ready_and_failed() -> None:
    tracker = EmbeddingLoadTracker("test-model")
    tracker.set_ready()
    assert tracker.snapshot()["status"] == "ready"
    tracker.set_failed("network error")
    snap = tracker.snapshot()
    assert snap["status"] == "failed"
    assert snap["error"] == "network error"


def test_embedding_model_for_ui_disabled() -> None:
    cfg = MemoryConfig(enabled=False)
    ui = embedding_model_for_ui(None, cfg)
    assert ui["status"] == "disabled"


def test_build_memory_payload_includes_embedding_model(tmp_path: Path) -> None:
    embedder = LocalEmbedder(MemoryConfig(enabled=True), tmp_path)
    payload = build_memory_payload(tmp_path, embedder=embedder, memory_config=MemoryConfig(enabled=True))
    assert "embeddingModel" in payload
    assert payload["embeddingModel"]["model"] == "Qwen/Qwen3-Embedding-0.6B"
    assert payload["embeddingModel"]["status"] in ("pending", "missing_deps", "ready")


def test_embedder_reports_ready_when_model_loaded(tmp_path: Path) -> None:
    embedder = LocalEmbedder(MemoryConfig(enabled=True), tmp_path)
    embedder._model = MagicMock()
    embedder._available = True
    status = embedder.get_load_status()
    assert status["status"] == "ready"


def test_embedder_download_with_progress(tmp_path: Path) -> None:
    embedder = LocalEmbedder(MemoryConfig(enabled=True), tmp_path)
    mock_st = MagicMock()
    with patch.object(embedder, "_has_sentence_transformers", return_value=True), patch.object(
        embedder, "_needs_download", return_value=True
    ), patch("huggingface_hub.snapshot_download") as mock_download, patch(
        "sentence_transformers.SentenceTransformer", return_value=mock_st
    ):
        mock_download.side_effect = lambda **kwargs: None
        model = embedder._load_model(allow_download=True)
    assert model is mock_st
    assert embedder.get_load_status()["status"] == "ready"
    mock_download.assert_called_once()
    call_kwargs = mock_download.call_args.kwargs
    assert call_kwargs.get("resume_download") is True


def test_partial_cache_triggers_download_not_loading_only(tmp_path: Path) -> None:
    """Metadata-only cache must still invoke snapshot_download."""
    cache = tmp_path / "memory" / ".embeddings_model"
    snap = cache / "models--Qwen--Qwen3-Embedding-0.6B" / "snapshots" / "abc"
    snap.mkdir(parents=True)
    (snap / "config.json").write_text("{}", encoding="utf-8")

    embedder = LocalEmbedder(MemoryConfig(enabled=True), tmp_path)
    assert embedder._is_model_cached() is False

    mock_st = MagicMock()
    with patch.object(embedder, "_has_sentence_transformers", return_value=True), patch(
        "huggingface_hub.snapshot_download"
    ) as mock_download, patch("sentence_transformers.SentenceTransformer", return_value=mock_st):
        mock_download.return_value = None
        embedder._load_model(allow_download=True)
    mock_download.assert_called_once()

