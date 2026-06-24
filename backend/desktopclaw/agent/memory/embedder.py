"""Local Qwen3-Embedding (sentence-transformers) with async + graceful fallback.

Qwen3-Embedding is instruction-aware (queries use the "query" prompt) and
MRL (Matryoshka) capable — we truncate to ``embedding_truncate_dim``.

The hot path (user-facing retrieval) calls :meth:`embed_query_async`, which
runs the model in a worker thread with a timeout. If the model is unavailable
or the call times out, callers fall back to keyword search — the agent loop is
never blocked and never crashes on embedder failure.
"""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from pathlib import Path

from loguru import logger

from desktopclaw.agent.memory.embedding_status import EmbeddingLoadTracker, make_progress_tqdm_class
from desktopclaw.agent.memory.model_cache import has_resumable_partial, is_model_cache_complete
from desktopclaw.config.schema import MemoryConfig

# Session-global LRU cache cap for query embeddings.
_QUERY_CACHE_MAX = 256


class LocalEmbedder:
    """Lazy-loaded local embedding model with async + cache + fallback."""

    def __init__(self, config: MemoryConfig, workspace: Path):
        self.config = config
        self.workspace = workspace
        self._model = None
        self._available: bool | None = None
        self._load_lock = asyncio.Lock()
        self._query_cache: OrderedDict[str, list[float]] = OrderedDict()
        self._dim: int = 0  # observed model dimension (after truncation)
        self.load_tracker = EmbeddingLoadTracker(config.embedding_model)
        self._sync_initial_status()

    # ------------------------------------------------------------------ #
    # Availability / model loading
    # ------------------------------------------------------------------ #
    @property
    def available(self) -> bool:
        if self._available is None:
            self._available = self._try_load() is not None
        return self._available

    @property
    def embedding_dim(self) -> int:
        """Observed output dimension (post-truncation). 0 until first encode."""
        return self._dim

    def _cache_dir(self) -> Path:
        if self.config.embedding_cache_dir:
            return Path(self.config.embedding_cache_dir).expanduser()
        return self.workspace / "memory" / ".embeddings_model"

    def _try_load(self):
        """Synchronously load the model. Returns the model or None.

        Never triggers a download on the hot path: if the model is not already
        cached locally, we return None and let the cold-path IndexWorker perform
        (and absorb the latency of) the download. This keeps user-facing query
        embedding bounded — a missing model degrades to keyword fallback instead
        of stalling on a multi-hundred-MB network fetch.
        """
        return self._load_model(allow_download=False)

    def _try_load_for_indexing(self):
        """Load the model for the cold-path indexer; downloads if not cached.

        Called only from the IndexWorker's worker thread, where a slow download
        is acceptable (it never blocks the event loop or the user).
        """
        return self._load_model(allow_download=True)

    def get_load_status(self) -> dict[str, object]:
        """Snapshot for API/UI — reflects live tracker unless model is already loaded."""
        if self._model is not None or self._available is True:
            self.load_tracker.set_ready()
        return self.load_tracker.snapshot()

    def _sync_initial_status(self) -> None:
        if self._has_sentence_transformers() is False:
            self.load_tracker.set_missing_deps()
            return
        cache = self._cache_dir()
        if self._is_model_cached():
            self.load_tracker.set_pending("嵌入模型已缓存，等待加载…")
        elif has_resumable_partial(cache, self.config.embedding_model):
            self.load_tracker.set_pending(
                "检测到未完成的下载，将在启动后续传…",
                resumed=True,
            )
        else:
            self.load_tracker.set_pending()

    def _needs_download(self, cache: Path) -> bool:
        """True when weights are missing and snapshot_download should run."""
        return not is_model_cache_complete(cache, self.config.embedding_model)

    def _download_model_with_progress(self, cache: Path) -> None:
        """Download model weights to cache with progress reporting (supports resume)."""
        from huggingface_hub import snapshot_download

        resumed = has_resumable_partial(cache, self.config.embedding_model)
        tqdm_class = make_progress_tqdm_class(self.load_tracker, resumed=resumed)
        self.load_tracker.set_downloading(0, resumed=resumed)
        kwargs: dict = {
            "repo_id": self.config.embedding_model,
            "cache_dir": str(cache),
            "tqdm_class": tqdm_class,
        }
        # resume_download is default-on in recent huggingface_hub; keep explicit for older pins.
        try:
            snapshot_download(**kwargs, resume_download=True)
        except TypeError:
            snapshot_download(**kwargs)

    def _load_model(self, *, allow_download: bool):
        if self._model is not None:
            self.load_tracker.set_ready()
            return self._model
        if not allow_download and not self._is_model_cached():
            if self._available is None:
                logger.info(
                    "Embedding model {} not cached; hot-path query embedding disabled "
                    "(keyword fallback active). The background indexer will download it.",
                    self.config.embedding_model,
                )
                self._available = False
                if self.load_tracker.snapshot()["status"] not in (
                    EmbeddingLoadTracker.STATUS_DOWNLOADING,
                    EmbeddingLoadTracker.STATUS_LOADING,
                ):
                    self.load_tracker.set_pending()
            return None
        if not self._has_sentence_transformers():
            logger.warning(
                "sentence-transformers not installed; memory retrieval uses keyword fallback. "
                "Install with: pip install 'desktopclaw[memory]'"
            )
            self.load_tracker.set_missing_deps()
            self._available = False
            return None
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            self.load_tracker.set_missing_deps()
            self._available = False
            return None
        try:
            cache = self._cache_dir()
            cache.mkdir(parents=True, exist_ok=True)
            if allow_download and self._needs_download(cache):
                self._download_model_with_progress(cache)
            self.load_tracker.set_loading()
            # Qwen3 prefers left-padding; harmless for other models.
            try:
                self._model = SentenceTransformer(
                    self.config.embedding_model,
                    cache_folder=str(cache),
                    tokenizer_kwargs={"padding_side": "left"},
                )
            except TypeError:
                # Older sentence-transformers doesn't accept tokenizer_kwargs.
                self._model = SentenceTransformer(
                    self.config.embedding_model, cache_folder=str(cache)
                )
            logger.info("Loaded embedding model {}", self.config.embedding_model)
            self._available = True
            self.load_tracker.set_ready()
            return self._model
        except Exception as exc:
            logger.exception("Failed to load embedding model {}", self.config.embedding_model)
            self.load_tracker.set_failed(str(exc))
            self._available = False
            return None

    async def preload(self) -> bool:
        """Background-warm the model without blocking the AgentLoop. Idempotent.

        Preload is allowed to download the model (it runs in a worker thread,
        so the event loop and user-facing turns are never blocked). A failed or
        absent model degrades to keyword fallback — preload never crashes the
        agent.
        """
        async with self._load_lock:
            if self._model is not None or self._available is True:
                return True
            # Retry after a prior failure (e.g. interrupted download).
            snap = self.load_tracker.snapshot()
            if snap["status"] == EmbeddingLoadTracker.STATUS_FAILED:
                cache = self._cache_dir()
                resumed = has_resumable_partial(cache, self.config.embedding_model)
                self.load_tracker.set_pending(
                    "准备重试下载…" if not resumed else "准备续传未完成的下载…",
                    resumed=resumed,
                )
            # Allow a previously-hot-path-disabled model to retry download here.
            self._available = None
            try:
                model = await asyncio.to_thread(self._try_load_for_indexing)
                self._available = model is not None
                return self._available
            except Exception as exc:
                logger.exception("Embedding model preload failed; using keyword fallback")
                self.load_tracker.set_failed(str(exc))
                self._available = False
                return False

    @staticmethod
    def _has_sentence_transformers() -> bool:
        try:
            import sentence_transformers  # noqa: F401
            return True
        except ImportError:
            return False

    def _is_model_cached(self) -> bool:
        """True when weight files are fully present on disk (not just metadata)."""
        try:
            return is_model_cache_complete(self._cache_dir(), self.config.embedding_model)
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    # Synchronous encode (used by the cold-path IndexWorker)
    # ------------------------------------------------------------------ #
    def _encode(self, text: str, *, is_query: bool) -> list[float] | None:
        # Respect an explicit "unavailable" verdict without attempting a load —
        # a failed/absent model must never trigger a download on the hot path.
        if self._available is False:
            return None
        model = self._try_load()
        if model is None:
            return None
        try:
            if is_query and self.config.embedding_query_prompt:
                vec = model.encode(
                    text,
                    prompt_name=self.config.embedding_query_prompt,
                    normalize_embeddings=True,
                )
            else:
                vec = model.encode(text, normalize_embeddings=True)
            dim = self.config.embedding_truncate_dim
            result = vec.tolist()
            if dim and len(result) > dim:
                result = result[:dim]
                # Re-normalize after truncation (Matryoshka still needs unit norm).
                norm = sum(x * x for x in result) ** 0.5
                if norm > 0:
                    result = [x / norm for x in result]
            if self._dim == 0 and result:
                self._dim = len(result)
            return result
        except Exception:
            logger.exception("Embedding failed for text len={}", len(text))
            return None

    def embed_query(self, text: str) -> list[float] | None:
        """Synchronous query embedding (instruction-aware). Returns None on failure."""
        if not text.strip():
            return None
        if text in self._query_cache:
            self._query_cache.move_to_end(text)
            return self._query_cache[text]
        result = self._encode(text, is_query=True)
        if result is not None:
            self._cache_query(text, result)
        return result

    def embed_document(self, text: str) -> list[float] | None:
        """Synchronous document embedding (no instruction prompt). For indexing."""
        if not text.strip():
            return None
        # Cold path: allowed to download the model if missing.
        if self._model is None and self._available is False:
            # Hot path previously marked it unavailable; cold path may still be
            # able to download — reset so _try_load_for_indexing gets a chance.
            self._available = None
        return self._encode_doc(text)

    def _encode_doc(self, text: str) -> list[float] | None:
        model = self._try_load_for_indexing()
        if model is None:
            return None
        try:
            vec = model.encode(text, normalize_embeddings=True)
            result = vec.tolist()
            dim = self.config.embedding_truncate_dim
            if dim and len(result) > dim:
                result = result[:dim]
                norm = sum(x * x for x in result) ** 0.5
                if norm > 0:
                    result = [x / norm for x in result]
            if self._dim == 0 and result:
                self._dim = len(result)
            return result
        except Exception:
            logger.exception("Document embedding failed for text len={}", len(text))
            return None

    def embed_document_batch(self, texts: list[str]) -> list[list[float] | None]:
        """Batch document embed (cold path). Respects embedding_batch_size."""
        # Cold path: may download the model if missing.
        if self._model is None and self._available is False:
            self._available = None
        model = self._try_load_for_indexing()
        if model is None:
            return [None] * len(texts)
        out: list[list[float] | None] = []
        batch_size = max(1, self.config.embedding_batch_size)
        for start in range(0, len(texts), batch_size):
            chunk = texts[start:start + batch_size]
            # Skip empty entries individually so batch indices line up.
            cleaned = [t if t and t.strip() else " " for t in chunk]
            try:
                vecs = model.encode(cleaned, normalize_embeddings=True)
                for raw in vecs:
                    res = raw.tolist()
                    dim = self.config.embedding_truncate_dim
                    if dim and len(res) > dim:
                        res = res[:dim]
                        norm = sum(x * x for x in res) ** 0.5
                        if norm > 0:
                            res = [x / norm for x in res]
                    if self._dim == 0 and res:
                        self._dim = len(res)
                    out.append(res)
            except Exception:
                logger.exception("Batch embed failed at offset {}", start)
                out.extend([None] * len(chunk))
        return out

    def _cache_query(self, text: str, vector: list[float]) -> None:
        self._query_cache[text] = vector
        self._query_cache.move_to_end(text)
        while len(self._query_cache) > _QUERY_CACHE_MAX:
            self._query_cache.popitem(last=False)

    # ------------------------------------------------------------------ #
    # Async (hot path) — never blocks, never raises
    # ------------------------------------------------------------------ #
    async def embed_query_async(self, text: str) -> list[float] | None:
        """Async query embed with timeout + LRU cache. Returns None on any failure.

        Used on the user-facing retrieval hot path. Callers must fall back to
        keyword search when this returns None.
        """
        if not text.strip():
            return None
        if text in self._query_cache:
            self._query_cache.move_to_end(text)
            return self._query_cache[text]
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self.embed_query, text),
                timeout=self.config.embedding_timeout_s,
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(
                "Query embed timed out after {}s (len={}); using keyword fallback",
                self.config.embedding_timeout_s, len(text),
            )
            return None
        except Exception:
            logger.exception("Async query embed failed; using keyword fallback")
            return None

    # Back-compat shim for any legacy callers expecting ``embed``.
    def embed(self, text: str) -> list[float] | None:
        return self.embed_query(text)

    def embed_batch(self, texts: list[str]) -> list[list[float] | None]:
        return self.embed_document_batch(texts)
