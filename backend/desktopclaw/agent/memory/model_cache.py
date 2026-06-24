"""Helpers for HuggingFace embedding model cache completeness and resume detection."""

from __future__ import annotations

from pathlib import Path

# Weight filenames commonly used by sentence-transformers / transformers repos.
_WEIGHT_FILENAMES = (
    "model.safetensors",
    "pytorch_model.bin",
    "model.bin",
)


def model_cache_dir(cache_root: Path, repo_id: str) -> Path | None:
    """Return the HF cache directory for *repo_id* under *cache_root*, if present."""
    if not cache_root.exists():
        return None
    model_name = repo_id.split("/")[-1]
    for entry in cache_root.iterdir():
        if entry.is_dir() and model_name in entry.name and entry.name.startswith("models--"):
            return entry
    return None


def _snapshot_has_weights(snapshot_dir: Path) -> bool:
    for name in _WEIGHT_FILENAMES:
        candidate = snapshot_dir / name
        if candidate.is_file() and candidate.stat().st_size > 1024:
            return True
    for weight in snapshot_dir.glob("*.safetensors"):
        if weight.is_file() and weight.stat().st_size > 1024:
            return True
    for weight in snapshot_dir.glob("*.bin"):
        if weight.is_file() and weight.stat().st_size > 1024:
            return True
    return False


def is_model_cache_complete(cache_root: Path, repo_id: str) -> bool:
    """True only when at least one snapshot contains non-trivial weight files."""
    model_dir = model_cache_dir(cache_root, repo_id)
    if model_dir is None:
        return False
    snapshots = model_dir / "snapshots"
    if not snapshots.is_dir():
        return False
    for snap in snapshots.iterdir():
        if snap.is_dir() and _snapshot_has_weights(snap):
            return True
    return False


def has_resumable_partial(cache_root: Path, repo_id: str) -> bool:
    """True when a partial download exists and snapshot_download can resume it."""
    if is_model_cache_complete(cache_root, repo_id):
        return False
    model_dir = model_cache_dir(cache_root, repo_id)
    if model_dir is None:
        return False

    blobs = model_dir / "blobs"
    if blobs.is_dir():
        for blob in blobs.iterdir():
            if blob.name.endswith(".incomplete"):
                return True
            if blob.is_file() and blob.stat().st_size > 0:
                return True

    snapshots = model_dir / "snapshots"
    if snapshots.is_dir():
        for snap in snapshots.iterdir():
            if snap.is_dir() and any(snap.iterdir()):
                return True
    return False
