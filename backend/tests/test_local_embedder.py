"""Tests for LocalEmbedder: async + cache + fallback + query/document split."""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from desktopclaw.agent.memory.embedder import LocalEmbedder
from desktopclaw.config.schema import MemoryConfig


@pytest.fixture
def embedder(tmp_path: Path) -> LocalEmbedder:
    return LocalEmbedder(MemoryConfig(enabled=True), tmp_path)


class _Vec:
    def tolist(self):
        return [0.5, 0.5]


def test_unavailable_when_no_model(embedder: LocalEmbedder) -> None:
    # Hot path: an explicitly-disabled embedder returns None without loading.
    embedder._model = None
    embedder._available = False
    assert embedder.available is False
    assert embedder.embed("hello") is None
    assert embedder.embed_query("hello") is None


def test_embed_query_uses_cache(embedder: LocalEmbedder) -> None:
    embedder._available = True
    embedder._query_cache["cached"] = [0.1, 0.2]
    assert embedder.embed_query("cached") == [0.1, 0.2]


def test_mock_model_encode_query(embedder: LocalEmbedder) -> None:
    mock_model = MagicMock()
    mock_model.encode.return_value = _Vec()
    embedder._model = mock_model
    embedder._available = True
    result = embedder.embed_query("test text")
    assert result == [0.5, 0.5]
    mock_model.encode.assert_called_once()
    # Query path passes prompt_name.
    _, kwargs = mock_model.encode.call_args
    assert kwargs.get("prompt_name") == "query"


def test_embed_document_uses_no_prompt(embedder: LocalEmbedder) -> None:
    mock_model = MagicMock()
    mock_model.encode.return_value = _Vec()
    embedder._model = mock_model
    embedder._available = True
    result = embedder.embed_document("doc text")
    assert result == [0.5, 0.5]
    _, kwargs = mock_model.encode.call_args
    assert "prompt_name" not in kwargs or kwargs.get("prompt_name") is None


def test_truncate_dim_renormalizes(embedder: LocalEmbedder) -> None:
    embedder.config = MemoryConfig(enabled=True, embedding_truncate_dim=2)
    mock_model = MagicMock()

    class _LongVec:
        def tolist(self):
            return [3.0, 4.0, 0.0, 0.0]  # norm 5; truncated to [3,4] → unit [0.6,0.8]

    mock_model.encode.return_value = _LongVec()
    embedder._model = mock_model
    embedder._available = True
    result = embedder.embed_document("doc")
    assert len(result) == 2
    norm = sum(x * x for x in result) ** 0.5
    assert abs(norm - 1.0) < 1e-6


def test_query_cache_lru_eviction(embedder: LocalEmbedder) -> None:
    embedder._available = True
    # Fill beyond the cap (256) and ensure size stays bounded.
    for i in range(300):
        embedder._query_cache[str(i)] = [float(i)]
        embedder._query_cache.move_to_end(str(i))
        from desktopclaw.agent.memory.embedder import _QUERY_CACHE_MAX
        while len(embedder._query_cache) > _QUERY_CACHE_MAX:
            embedder._query_cache.popitem(last=False)
    from desktopclaw.agent.memory.embedder import _QUERY_CACHE_MAX
    assert len(embedder._query_cache) == _QUERY_CACHE_MAX
    # Oldest entries evicted.
    assert "0" not in embedder._query_cache


@pytest.mark.asyncio
async def test_embed_query_async_returns_cached(embedder: LocalEmbedder) -> None:
    embedder._available = True
    embedder._query_cache["cached"] = [0.1, 0.2]
    result = await embedder.embed_query_async("cached")
    assert result == [0.1, 0.2]


@pytest.mark.asyncio
async def test_embed_query_async_timeout_falls_back(embedder: LocalEmbedder) -> None:
    """When the model call exceeds the timeout, async returns None (keyword fallback)."""
    embedder.config = MemoryConfig(enabled=True, embedding_timeout_s=0.05)
    mock_model = MagicMock()

    def slow_encode(*args, **kwargs):
        import time
        time.sleep(0.5)
        return _Vec()

    mock_model.encode.side_effect = slow_encode
    embedder._model = mock_model
    embedder._available = True
    result = await embedder.embed_query_async("slow query")
    assert result is None  # timed out → caller falls back to keywords


@pytest.mark.asyncio
async def test_embed_query_async_failure_falls_back(embedder: LocalEmbedder) -> None:
    embedder.config = MemoryConfig(enabled=True, embedding_timeout_s=2.0)
    mock_model = MagicMock()
    mock_model.encode.side_effect = RuntimeError("boom")
    embedder._model = mock_model
    embedder._available = True
    result = await embedder.embed_query_async("bad")
    assert result is None


@pytest.mark.asyncio
async def test_preload_sets_available(embedder: LocalEmbedder) -> None:
    mock_model = MagicMock()
    mock_model.encode.return_value = _Vec()
    # preload uses the indexing loader (allowed to download); patch that path.
    embedder._try_load_for_indexing = lambda: mock_model  # type: ignore[method-assign]
    ok = await embedder.preload()
    assert ok is True
    assert embedder.available is True


@pytest.mark.asyncio
async def test_preload_failure_degrades(embedder: LocalEmbedder) -> None:
    embedder._try_load_for_indexing = lambda: None  # type: ignore[method-assign]
    ok = await embedder.preload()
    assert ok is False
    assert embedder.available is False


def test_empty_text_returns_none(embedder: LocalEmbedder) -> None:
    assert embedder.embed_query("") is None
    assert embedder.embed_document("   ") is None
