"""Lightweight integration test for memory-enabled AgentLoop."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from desktopclaw.agent.loop import AgentLoop
from desktopclaw.bus.queue import MessageBus
from desktopclaw.config.schema import MemoryConfig
from desktopclaw.providers.base import LLMProvider, LLMResponse


class StaticProvider(LLMProvider):
    async def chat(self, *args, **kwargs) -> LLMResponse:
        return LLMResponse(content="Done.", tool_calls=[])

    def get_default_model(self) -> str:
        return "test-model"


@pytest.mark.asyncio
async def test_agent_loop_with_memory_disabled(tmp_path: Path) -> None:
    bus = MessageBus()
    provider = StaticProvider()
    loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=tmp_path,
        model="test-model",
        memory_config=MemoryConfig(enabled=False),
    )
    result = await loop.process_direct("hello")
    assert "Done" in result.content
