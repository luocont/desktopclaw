"""Tests for GET /memory API."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from desktopclaw.api.memory_helpers import build_memory_payload, strategy_unit_for_ui
from desktopclaw.api.server import APIServer
from desktopclaw.config.schema import MemoryConfig


def test_strategy_unit_for_ui_strips_embedding() -> None:
    raw = {
        "id": "u1",
        "title": "Test",
        "description": "d",
        "content": "c",
        "kind": "strategy",
        "domain": "general",
        "tools": [],
        "confidence": 0.8,
        "source": "distilled",
        "created_at": "2026-01-01T00:00:00Z",
        "hit_count": 0,
        "embedding": [0.1, 0.2, 0.3],
        "index_status": "ready",
        "index_error": "",
        "index_attempts": 1,
        "embedding_model": "test",
        "embedding_dim": 3,
    }
    ui = strategy_unit_for_ui(raw)
    assert "embedding" not in ui
    assert "indexAttempts" not in ui
    assert ui["indexStatus"] == "ready"
    assert ui["createdAt"] == "2026-01-01T00:00:00Z"


def test_build_memory_payload_empty(tmp_path) -> None:
    payload = build_memory_payload(tmp_path, memory_config=MemoryConfig(enabled=True))
    assert payload["success"] is True
    assert payload["userMemory"]["markdown"] == ""
    assert payload["strategies"] == []
    assert payload["stats"]["strategyCount"] == 0
    assert payload["embeddingModel"]["status"] == "pending"


def test_build_memory_payload_with_files(tmp_path) -> None:
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "MEMORY.md").write_text("# User\nLikes dark mode", encoding="utf-8")
    (memory_dir / "HISTORY.md").write_text("[2026-01-01] did something", encoding="utf-8")
    (memory_dir / "reasoning_bank.json").write_text(
        json.dumps([
            {
                "id": "s1",
                "title": "Win UTF-8",
                "description": "When exec garbled",
                "content": "Set UTF-8",
                "kind": "strategy",
                "domain": "shell",
                "tools": ["exec"],
                "confidence": 0.9,
                "source": "distilled",
                "created_at": "2026-01-01T00:00:00Z",
                "hit_count": 2,
                "embedding": [1.0, 0.0],
                "index_status": "ready",
            },
        ]),
        encoding="utf-8",
    )
    payload = build_memory_payload(tmp_path)
    assert "dark mode" in payload["userMemory"]["markdown"]
    assert len(payload["strategies"]) == 1
    assert payload["strategies"][0]["title"] == "Win UTF-8"
    assert "embedding" not in payload["strategies"][0]
    assert payload["stats"]["readyCount"] == 1


@pytest.mark.asyncio
async def test_handle_get_memory(tmp_path, monkeypatch) -> None:
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    (memory_dir / "MEMORY.md").write_text("hello memory", encoding="utf-8")

    config = MagicMock()
    config.workspace_path = tmp_path
    config.agents.memory = MemoryConfig(enabled=True)
    monkeypatch.setattr("desktopclaw.api.server.load_config", lambda: config)

    agent = MagicMock()
    agent._memory_services = MagicMock(embedder=None)
    server = APIServer(agent=agent, bus=MagicMock(), port=3000)

    writer = MagicMock()
    written: list[bytes] = []
    writer.write = lambda data: written.append(data)
    writer.drain = AsyncMock()

    await server._handle_get_memory(writer)
    body = written[-1].decode("utf-8").split("\r\n\r\n", 1)[1]
    data = json.loads(body)
    assert data["success"] is True
    assert data["userMemory"]["markdown"] == "hello memory"
    assert data["embeddingModel"]["status"] == "pending"
