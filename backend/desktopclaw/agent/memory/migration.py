"""Initialize agent memory storage on first run + embedding model migration."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from desktopclaw.utils.helpers import ensure_dir


def ensure_memory_layout(workspace: Path) -> Path:
    """Ensure memory directory and empty reasoning bank exist."""
    memory_dir = ensure_dir(workspace / "memory")
    bank_file = memory_dir / "reasoning_bank.json"
    if not bank_file.exists():
        bank_file.write_text("[]", encoding="utf-8")
    ensure_dir(memory_dir / ".embeddings_model")
    return memory_dir


def migrate_embedding_model(
    memory_dir: Path,
    current_model: str,
    current_dim: int = 0,
) -> int:
    """Mark units stale when the embedding model or dim changed.

    Runs synchronously at startup. Units whose ``embedding_model`` differs from
    the configured one (or whose ``embedding_dim`` no longer matches) are reset
    to ``index_status="pending"`` with their embedding cleared. The background
    IndexWorker picks them up via ``recover_pending()`` and rebuilds them.

    Returns the number of units scheduled for reindex.
    """
    bank_file = memory_dir / "reasoning_bank.json"
    if not bank_file.exists():
        return 0

    # Imported lazily to avoid a circular import with factory/reasoning_bank.
    from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore
    from desktopclaw.agent.memory.types import ReasoningUnit

    bank = ReasoningBankStore(bank_file)
    units = bank.list_units()
    if not units:
        return 0

    stale: list[ReasoningUnit] = []
    for unit in units:
        model_mismatch = unit.embedding_model and unit.embedding_model != current_model
        # Dim mismatch only matters when the model itself matches — otherwise the
        # model change already forces a reindex and a foreign dim is expected.
        dim_mismatch = (
            not model_mismatch
            and unit.embedding_model == current_model
            and current_dim
            and unit.embedding_dim
            and unit.embedding_dim != current_dim
        )
        if model_mismatch or dim_mismatch:
            stale.append(unit)

    if not stale:
        return 0

    for unit in stale:
        unit.embedding = None
        unit.embedding_model = ""
        unit.embedding_dim = 0
        unit.index_status = "pending"
        unit.index_error = ""
        unit.index_attempts = 0
        bank.update_unit(unit)
    logger.info(
        "Embedding model migration: {} units marked pending for reindex (model={}, dim={})",
        len(stale), current_model, current_dim,
    )
    return len(stale)
