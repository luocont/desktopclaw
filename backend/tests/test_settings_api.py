"""Tests for GET/POST /settings fastModelId round-trip."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest

from desktopclaw.api.server import APIServer
from desktopclaw.config.loader import load_config, save_config
from desktopclaw.config.schema import Config


@pytest.mark.asyncio
async def test_settings_fast_model_id_round_trip(tmp_path, monkeypatch) -> None:
    config_path = tmp_path / "config.json"
    config = Config()
    config.agents.defaults.model = "main-model"
    config.agents.defaults.fast_model = "fast-model"
    save_config(config, config_path)

    monkeypatch.setattr("desktopclaw.config.loader.get_config_path", lambda: config_path)
    monkeypatch.setattr("desktopclaw.api.server.load_config", lambda: load_config(config_path))
    monkeypatch.setattr("desktopclaw.api.server.save_config", lambda cfg: save_config(cfg, config_path))

    server = APIServer(agent=MagicMock(), bus=MagicMock(), port=3000)

    reader = asyncio.StreamReader()
    writer = MagicMock()
    written: list[bytes] = []

    async def fake_drain() -> None:
        return None

    writer.write = lambda data: written.append(data)
    writer.drain = fake_drain

    await server._handle_get_settings(writer)
    body = written[-1].decode("utf-8").split("\r\n\r\n", 1)[1]
    payload = json.loads(body)
    assert payload["modelId"] == "main-model"
    assert payload["fastModelId"] == "fast-model"

    post_body = json.dumps({"fastModelId": "new-fast-model"}).encode("utf-8")
    post_reader = asyncio.StreamReader()
    post_reader.feed_data(post_body)
    post_reader.feed_eof()

    post_writer = MagicMock()
    post_written: list[bytes] = []
    post_writer.write = lambda data: post_written.append(data)
    post_writer.drain = fake_drain

    headers = {"content-length": str(len(post_body))}
    await server._handle_set_settings(post_reader, post_writer, headers)

    reloaded = load_config(config_path)
    assert reloaded.agents.defaults.fast_model == "new-fast-model"
