"""Thread-safe embedding model load/download status for UI reporting."""

from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass
class _State:
    status: str = "pending"
    progress: float | None = None
    message: str = ""
    error: str = ""
    resumed: bool = False


class EmbeddingLoadTracker:
    """Tracks embedding model download/load progress (thread-safe)."""

    STATUS_READY = "ready"
    STATUS_PENDING = "pending"
    STATUS_DOWNLOADING = "downloading"
    STATUS_LOADING = "loading"
    STATUS_FAILED = "failed"
    STATUS_MISSING_DEPS = "missing_deps"

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._lock = threading.Lock()
        self._state = _State(message="等待下载嵌入模型…")

    def set_pending(self, message: str = "等待下载嵌入模型…", *, resumed: bool = False) -> None:
        with self._lock:
            self._state = _State(
                status=self.STATUS_PENDING,
                progress=None,
                message=message,
                resumed=resumed,
            )

    def set_downloading(
        self,
        progress: float,
        message: str = "",
        *,
        resumed: bool = False,
    ) -> None:
        with self._lock:
            if not message:
                verb = "续传" if resumed else "下载"
                message = f"正在{verb}嵌入模型… {progress:.0f}%"
            self._state = _State(
                status=self.STATUS_DOWNLOADING,
                progress=max(0.0, min(100.0, progress)),
                message=message,
                resumed=resumed,
            )

    def set_loading(self, message: str = "正在加载嵌入模型…") -> None:
        with self._lock:
            self._state = _State(status=self.STATUS_LOADING, progress=None, message=message)

    def set_ready(self, message: str = "嵌入模型已就绪") -> None:
        with self._lock:
            self._state = _State(status=self.STATUS_READY, progress=100.0, message=message)

    def set_failed(self, error: str, message: str = "嵌入模型加载失败") -> None:
        with self._lock:
            self._state = _State(
                status=self.STATUS_FAILED,
                progress=None,
                message=message,
                error=error[:500],
            )

    def set_missing_deps(self, message: str = "未安装 sentence-transformers") -> None:
        with self._lock:
            self._state = _State(
                status=self.STATUS_MISSING_DEPS,
                progress=None,
                message=message,
                error="pip install 'desktopclaw[memory]'",
            )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "status": self._state.status,
                "progress": self._state.progress,
                "model": self.model_name,
                "message": self._state.message,
                "error": self._state.error,
                "resumed": self._state.resumed,
            }


def make_progress_tqdm_class(tracker: EmbeddingLoadTracker, *, resumed: bool = False):
    """Build a huggingface_hub-compatible tqdm class that reports download progress."""

    try:
        from tqdm.auto import tqdm as BaseTqdm
    except ImportError:
        BaseTqdm = None  # type: ignore[misc, assignment]

    class ProgressTqdm(BaseTqdm if BaseTqdm else object):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            if BaseTqdm:
                super().__init__(*args, **kwargs)
            else:
                self.n = 0
                self.total = kwargs.get("total") or 0
            self._tracker = tracker
            self._resumed = resumed
            self._report()

        def update(self, n=1):
            if BaseTqdm:
                result = super().update(n)
            else:
                self.n = getattr(self, "n", 0) + n
                result = None
            self._report()
            return result

        def _report(self) -> None:
            total = getattr(self, "total", None) or 0
            current = getattr(self, "n", 0)
            if total and total > 0:
                pct = current / total * 100.0
                self._tracker.set_downloading(pct, resumed=self._resumed)
            else:
                verb = "续传" if self._resumed else "下载"
                self._tracker.set_downloading(0, message=f"正在{verb}嵌入模型…", resumed=self._resumed)

    return ProgressTqdm
