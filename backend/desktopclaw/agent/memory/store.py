"""User fact memory: MEMORY.md + HISTORY.md."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from loguru import logger

from desktopclaw.utils.helpers import ensure_dir

from desktopclaw.agent.memory.prompts import MEMORY_LANGUAGE_RULE

if TYPE_CHECKING:
    from desktopclaw.providers.base import LLMProvider


_SAVE_MEMORY_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_memory",
            "description": "将记忆归档结果写入持久化存储。history_entry 与 memory_update 须使用中文（简体）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "history_entry": {
                        "type": "string",
                        "description": "一段中文摘要，概括关键事件/决策/主题。"
                        "以 [YYYY-MM-DD HH:MM] 开头，便于 grep 检索。",
                    },
                    "memory_update": {
                        "type": "string",
                        "description": "更新后的完整长期记忆（Markdown，中文）。"
                        "保留已有事实并补充新内容；若无新信息则返回原内容。",
                    },
                },
                "required": ["history_entry", "memory_update"],
            },
        },
    }
]


def _ensure_text(value: Any) -> str:
    """Normalize tool-call payload values to text for file storage."""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def _normalize_save_memory_args(args: Any) -> dict[str, Any] | None:
    """Normalize provider tool-call arguments to the expected dict shape."""
    if isinstance(args, str):
        args = json.loads(args)
    if isinstance(args, list):
        return args[0] if args and isinstance(args[0], dict) else None
    return args if isinstance(args, dict) else None


class MemoryStore:
    """Two-layer memory: MEMORY.md (long-term facts) + HISTORY.md (grep-searchable log)."""

    def __init__(self, workspace: Path):
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
        self.history_file = self.memory_dir / "HISTORY.md"

    def read_long_term(self) -> str:
        if self.memory_file.exists():
            return self.memory_file.read_text(encoding="utf-8")
        return ""

    def write_long_term(self, content: str) -> None:
        self.memory_file.write_text(content, encoding="utf-8")

    def append_history(self, entry: str) -> None:
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(entry.rstrip() + "\n\n")

    def get_memory_context(self) -> str:
        long_term = self.read_long_term()
        return f"## Long-term Memory\n{long_term}" if long_term else ""

    @staticmethod
    def _format_messages(messages: list[dict]) -> str:
        lines = []
        for message in messages:
            if not message.get("content"):
                continue
            tools = f" [tools: {', '.join(message['tools_used'])}]" if message.get("tools_used") else ""
            lines.append(
                f"[{message.get('timestamp', '?')[:16]}] {message['role'].upper()}{tools}: {message['content']}"
            )
        return "\n".join(lines)

    async def consolidate(
        self,
        messages: list[dict],
        provider: LLMProvider,
        model: str,
    ) -> bool:
        """Consolidate the provided message chunk into MEMORY.md + HISTORY.md."""
        if not messages:
            return True

        current_memory = self.read_long_term()
        prompt = f"""处理以下对话，调用 save_memory 工具完成记忆归档。

{MEMORY_LANGUAGE_RULE}

## 当前长期记忆
{current_memory or "（空）"}

## 待处理对话
{self._format_messages(messages)}"""

        chat_messages = [
            {
                "role": "system",
                "content": (
                    "你是用户事实记忆归档助手。"
                    f"{MEMORY_LANGUAGE_RULE} "
                    "请调用 save_memory 提交归档结果。"
                ),
            },
            {"role": "user", "content": prompt},
        ]

        try:
            response = await provider.chat_with_retry(
                messages=chat_messages,
                tools=_SAVE_MEMORY_TOOL,
                model=model,
                tool_choice="auto",
            )

            if not response.has_tool_calls:
                logger.warning("Memory consolidation: LLM did not call save_memory, skipping")
                return False

            args = _normalize_save_memory_args(response.tool_calls[0].arguments)
            if args is None:
                logger.warning("Memory consolidation: unexpected save_memory arguments")
                return False

            if entry := args.get("history_entry"):
                self.append_history(_ensure_text(entry))
            if update := args.get("memory_update"):
                update = _ensure_text(update)
                if update != current_memory:
                    self.write_long_term(update)

            logger.info("Memory consolidation done for {} messages", len(messages))
            return True
        except Exception:
            logger.exception("Memory consolidation failed")
            return False
