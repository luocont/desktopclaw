"""Tests for session list/messages API and sessionKey in /chat."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from desktopclaw.api.server import APIServer
from desktopclaw.api.session_helpers import session_messages_for_ui
from desktopclaw.session.ui_messages import messages_to_ui_blocks
from desktopclaw.session.manager import Session, SessionManager


def test_session_message_for_ui_maps_roles() -> None:
    assert messages_to_ui_blocks([{"role": "user", "content": "hi"}]) == [
        {"role": "user", "content": "hi"},
    ]
    assert messages_to_ui_blocks([{"role": "assistant", "content": "hello"}]) == [
        {"role": "ai", "blockType": "reply", "content": "hello"},
    ]
    assert messages_to_ui_blocks([{"role": "system", "content": "ignored"}]) == []


def test_session_messages_for_ui_skips_system() -> None:
    session = Session(key="api:frontend:api")
    session.add_message("user", "one")
    session.add_message("assistant", "two")
    session.messages.append({"role": "system", "content": "hidden"})
    ui = session_messages_for_ui(session)
    assert len(ui) == 2
    assert ui[0]["role"] == "user"
    assert ui[1]["blockType"] == "reply"


def test_messages_to_ui_blocks_tool_and_spawn() -> None:
    messages = [
        {"role": "user", "content": "search"},
        {
            "role": "assistant",
            "reasoning_content": "need to search",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "web_search", "arguments": '{"query": "test"}'},
                },
                {
                    "id": "call_2",
                    "type": "function",
                    "function": {
                        "name": "spawn",
                        "arguments": '{"task": "long task", "label": "research"}',
                    },
                },
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "name": "web_search", "content": "results"},
        {
            "role": "tool",
            "tool_call_id": "call_2",
            "name": "spawn",
            "content": "Subagent [research] started (id: abc).",
        },
        {"role": "assistant", "content": "done"},
    ]
    ui = messages_to_ui_blocks(messages)
    assert ui[0] == {"role": "user", "content": "search"}
    assert ui[1]["blockType"] == "thinking"
    assert ui[1]["collapsed"] is True
    assert ui[2]["blockType"] == "tool"
    assert ui[2]["meta"]["result"] == "results"
    assert ui[3]["blockType"] == "subagent"
    assert ui[3]["meta"]["label"] == "research"
    assert ui[4]["blockType"] == "reply"
    assert ui[4]["content"] == "done"


@pytest.mark.asyncio
async def test_list_sessions_filters_frontend_prefix(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    main = manager.get_or_create("api:frontend:api")
    main.add_message("user", "hello")
    manager.save(main)
    other = manager.get_or_create("cli:direct")
    other.add_message("user", "cli msg")
    manager.save(other)

    agent = MagicMock()
    agent.sessions = manager
    server = APIServer(agent=agent, bus=MagicMock(), port=3000)

    writer = MagicMock()
    written: list[bytes] = []
    writer.write = lambda data: written.append(data)
    writer.drain = AsyncMock()

    await server._handle_list_sessions(writer)
    body = written[-1].decode("utf-8").split("\r\n\r\n", 1)[1]
    payload = json.loads(body)
    assert payload["success"] is True
    keys = {s["key"] for s in payload["sessions"]}
    assert "api:frontend:api" in keys
    assert "cli:direct" not in keys


@pytest.mark.asyncio
async def test_get_session_messages_returns_ui_messages(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("api:frontend:api")
    session.add_message("user", "question")
    session.add_message("assistant", "answer")
    manager.save(session)

    agent = MagicMock()
    agent.sessions = manager
    server = APIServer(agent=agent, bus=MagicMock(), port=3000)

    writer = MagicMock()
    written: list[bytes] = []
    writer.write = lambda data: written.append(data)
    writer.drain = AsyncMock()

    await server._handle_get_session_messages(writer, "api:frontend:api")
    body = written[-1].decode("utf-8").split("\r\n\r\n", 1)[1]
    payload = json.loads(body)
    assert payload["success"] is True
    assert payload["key"] == "api:frontend:api"
    assert payload["messages"] == [
        {"role": "user", "content": "question"},
        {"role": "ai", "blockType": "reply", "content": "answer"},
    ]


@pytest.mark.asyncio
async def test_get_session_messages_rejects_non_frontend_key(tmp_path) -> None:
    agent = MagicMock()
    agent.sessions = SessionManager(tmp_path)
    server = APIServer(agent=agent, bus=MagicMock(), port=3000)

    writer = MagicMock()
    written: list[bytes] = []
    writer.write = lambda data: written.append(data)
    writer.drain = AsyncMock()

    await server._handle_get_session_messages(writer, "cli:direct")
    status_line = written[-1].decode("utf-8").split("\r\n", 1)[0]
    assert "403" in status_line


@pytest.mark.asyncio
async def test_delete_session_removes_file(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("api:frontend:conv_1")
    session.add_message("user", "hello")
    manager.save(session)

    agent = MagicMock()
    agent.sessions = manager
    server = APIServer(agent=agent, bus=MagicMock(), port=3000)

    writer = MagicMock()
    written: list[bytes] = []
    writer.write = lambda data: written.append(data)
    writer.drain = AsyncMock()

    await server._handle_delete_session(writer, "api:frontend:conv_1")
    status_line = written[-1].decode("utf-8").split("\r\n", 1)[0]
    body = written[-1].decode("utf-8").split("\r\n\r\n", 1)[1]
    payload = json.loads(body)
    assert "200" in status_line
    assert payload["success"] is True
    assert manager.delete("api:frontend:conv_1") is False
    keys = {s["key"] for s in manager.list_sessions()}
    assert "api:frontend:conv_1" not in keys


@pytest.mark.asyncio
async def test_delete_session_rejects_non_frontend_key(tmp_path) -> None:
    manager = SessionManager(tmp_path)
    session = manager.get_or_create("cli:direct")
    session.add_message("user", "hello")
    manager.save(session)

    agent = MagicMock()
    agent.sessions = manager
    server = APIServer(agent=agent, bus=MagicMock(), port=3000)

    writer = MagicMock()
    written: list[bytes] = []
    writer.write = lambda data: written.append(data)
    writer.drain = AsyncMock()

    await server._handle_delete_session(writer, "cli:direct")
    status_line = written[-1].decode("utf-8").split("\r\n", 1)[0]
    assert "403" in status_line


def test_resolve_session_key_defaults() -> None:
    assert APIServer._resolve_session_key("api") == "api:frontend:api"
    assert APIServer._resolve_session_key("api", "api:frontend:conv_1") == "api:frontend:conv_1"


def test_build_complete_event_includes_blocks() -> None:
    from desktopclaw.agent.loop import ProcessResult

    result = ProcessResult(
        content="hello",
        usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2, "breakdown": {}},
        blocks=[{"role": "ai", "blockType": "thinking", "content": "thought", "collapsed": True}],
    )
    event = APIServer._build_complete_event(result)
    assert event["blocks"][0]["blockType"] == "thinking"
