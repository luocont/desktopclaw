"""Serialize workspace memory for the frontend GET /memory API."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore
from desktopclaw.config.schema import MemoryConfig

if TYPE_CHECKING:
    from desktopclaw.agent.memory.embedder import LocalEmbedder

HISTORY_PREVIEW_CHARS = 2000


def _snake_to_camel(key: str) -> str:
    parts = key.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


def strategy_unit_for_ui(unit_dict: dict) -> dict:
    """Convert ReasoningUnit dict to camelCase API payload without embedding."""
    skip = {"embedding", "index_attempts", "embedding_model", "embedding_dim"}
    out: dict = {}
    for key, value in unit_dict.items():
        if key in skip:
            continue
        out[_snake_to_camel(key)] = value
    return out


def embedding_model_for_ui(
    embedder: LocalEmbedder | None,
    memory_config: MemoryConfig | None = None,
) -> dict:
    """Build camelCase embedding model status for the memory page."""
    if memory_config is not None and not memory_config.enabled:
        return {
            "status": "disabled",
            "progress": None,
            "model": "",
            "message": "策略记忆已关闭",
            "error": "",
            "resumed": False,
        }
    if embedder is not None:
        snap = embedder.get_load_status()
        return {
            "status": snap["status"],
            "progress": snap["progress"],
            "model": snap["model"],
            "message": snap["message"],
            "error": snap.get("error", ""),
            "resumed": snap.get("resumed", False),
        }
    model = memory_config.embedding_model if memory_config else ""
    return {
        "status": "pending",
        "progress": None,
        "model": model,
        "message": "等待嵌入模型状态…",
        "error": "",
        "resumed": False,
    }


def build_memory_payload(
    workspace: Path,
    embedder: LocalEmbedder | None = None,
    memory_config: MemoryConfig | None = None,
) -> dict:
    """Read user + strategy memory from workspace for API response."""
    memory_dir = workspace / "memory"
    memory_file = memory_dir / "MEMORY.md"
    history_file = memory_dir / "HISTORY.md"
    bank_file = memory_dir / "reasoning_bank.json"

    markdown = ""
    if memory_file.exists():
        markdown = memory_file.read_text(encoding="utf-8")

    history_preview = ""
    if history_file.exists():
        raw = history_file.read_text(encoding="utf-8")
        if len(raw) > HISTORY_PREVIEW_CHARS:
            history_preview = raw[-HISTORY_PREVIEW_CHARS:]
        else:
            history_preview = raw

    strategies: list[dict] = []
    pending = ready = failed = 0
    if bank_file.exists():
        bank = ReasoningBankStore(bank_file)
        for unit in bank.list_units():
            data = strategy_unit_for_ui(unit.to_dict())
            strategies.append(data)
            status = data.get("indexStatus", "pending")
            if status == "ready":
                ready += 1
            elif status == "failed":
                failed += 1
            else:
                pending += 1

    return {
        "success": True,
        "userMemory": {
            "markdown": markdown,
            "historyPreview": history_preview,
        },
        "strategies": strategies,
        "stats": {
            "strategyCount": len(strategies),
            "pendingCount": pending,
            "readyCount": ready,
            "failedCount": failed,
        },
        "embeddingModel": embedding_model_for_ui(embedder, memory_config),
    }
