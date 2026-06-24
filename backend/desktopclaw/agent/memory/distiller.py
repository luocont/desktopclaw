"""Post-task strategy distillation into ReasoningBank."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from loguru import logger

from desktopclaw.agent.memory.prompts import MEMORY_LANGUAGE_RULE
from desktopclaw.agent.memory.types import ReasoningUnit, TaskOutcome

if TYPE_CHECKING:
    from desktopclaw.agent.memory.graph_builder import GraphBuilder
    from desktopclaw.agent.memory.index_worker import MemoryIndexWorker
    from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore
    from desktopclaw.config.schema import MemoryConfig
    from desktopclaw.providers.base import LLMProvider

_SAVE_UNITS_TOOL = [
    {
        "type": "function",
        "function": {
            "name": "save_reasoning_units",
            "description": "保存从已完成任务中蒸馏出的推理策略单元。所有文本字段须使用中文（简体）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "units": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "策略标题（中文）"},
                                "description": {"type": "string", "description": "适用场景简述（中文）"},
                                "content": {"type": "string", "description": "具体推理步骤与原则（中文）"},
                                "kind": {"type": "string", "enum": ["strategy", "pitfall"]},
                                "domain": {"type": "string", "description": "任务领域（中文或简短英文标识）"},
                                "tools": {"type": "array", "items": {"type": "string"}},
                            },
                            "required": ["title", "description", "content", "kind"],
                        },
                    },
                    "task_outcome": {
                        "type": "string",
                        "enum": ["success", "partial", "failure"],
                    },
                    "confidence": {"type": "number"},
                },
                "required": ["units", "task_outcome", "confidence"],
            },
        },
    }
]

_ERROR_MARKERS = ("error", "failed", "failure", "exception", "traceback")


class StrategyDistiller:
    """Distill reasoning strategies from completed agent turns."""

    def __init__(
        self,
        bank: ReasoningBankStore,
        graph_builder: GraphBuilder,
        embedder,
        provider: LLMProvider,
        model: str,
        config: MemoryConfig,
        index_worker: MemoryIndexWorker | None = None,
    ):
        self.bank = bank
        self.graph_builder = graph_builder
        self.embedder = embedder
        self.provider = provider
        self.model = model
        self.config = config
        self.index_worker = index_worker

    @property
    def enabled(self) -> bool:
        return self.config.enabled and self.config.distillation

    @staticmethod
    def infer_outcome(
        tools_used: list[str],
        messages: list[dict],
        hit_max_iterations: bool,
    ) -> TaskOutcome:
        if hit_max_iterations:
            return "partial"
        for msg in messages:
            if msg.get("role") == "tool":
                content = (msg.get("content") or "").lower()
                if any(m in content for m in _ERROR_MARKERS):
                    return "failure"
            if msg.get("role") == "assistant" and msg.get("finish_reason") == "error":
                return "failure"
        if tools_used:
            return "success"
        return "success"

    @staticmethod
    def _summarize_messages(messages: list[dict], max_chars: int = 8000) -> str:
        lines: list[str] = []
        total = 0
        for msg in messages:
            role = msg.get("role", "?")
            content = msg.get("content") or ""
            if isinstance(content, list):
                content = str(content)
            if role == "tool" and len(content) > 500:
                content = content[:500] + "... (truncated)"
            line = f"{role}: {content}"
            if total + len(line) > max_chars:
                break
            lines.append(line)
            total += len(line)
        return "\n".join(lines)

    async def distill_from_turn(
        self,
        session_key: str,
        user_message: str,
        messages: list[dict],
        tools_used: list[str],
        hit_max_iterations: bool = False,
    ) -> None:
        if not self.enabled:
            return
        outcome = self.infer_outcome(tools_used, messages, hit_max_iterations)
        await self._distill(user_message, messages, tools_used, outcome, source="main")

    async def distill_from_subagent(
        self,
        task: str,
        messages: list[dict],
        status: str,
    ) -> None:
        if not self.enabled:
            return
        outcome: TaskOutcome = "failure" if status == "error" else "success"
        tools_used = [
            m.get("name", "")
            for m in messages
            if m.get("role") == "tool" and m.get("name")
        ]
        await self._distill(task, messages, tools_used, outcome, source="subagent")

    async def _distill(
        self,
        user_message: str,
        messages: list[dict],
        tools_used: list[str],
        outcome: TaskOutcome,
        source: str,
    ) -> None:
        summary = self._summarize_messages(messages)
        prompt = f"""分析以下 Agent 任务，蒸馏可复用的推理策略写入记忆库。

{MEMORY_LANGUAGE_RULE}

任务: {user_message}
结果: {outcome}
使用工具: {', '.join(tools_used) or '无'}
来源: {source}

对话记录:
{summary}

提取 0-2 条简洁的策略单元：
- 成功时: kind=strategy，记录可复用的决策逻辑
- 失败/部分完成时: kind=pitfall，记录根因与规避规则
无战略价值的闲聊可跳过（units 可为空）。请调用 save_reasoning_units。"""

        try:
            response = await self.provider.chat_with_retry(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是 Agent 推理策略记忆蒸馏器。"
                            f"{MEMORY_LANGUAGE_RULE} "
                            "请调用 save_reasoning_units 保存结果。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                tools=_SAVE_UNITS_TOOL,
                model=self.model,
                temperature=0,
                # Thinking models (e.g. DeepSeek) reject forced tool_choice; auto works.
                tool_choice="auto",
            )
            if not response.has_tool_calls:
                return
            args = response.tool_calls[0].arguments
            if isinstance(args, str):
                args = json.loads(args)
            if not isinstance(args, dict):
                return
            await self._persist_units(args, outcome)
        except Exception:
            logger.exception("Strategy distillation failed")

    async def _persist_units(self, args: dict[str, Any], outcome: TaskOutcome) -> None:
        confidence = float(args.get("confidence", 0))
        if confidence < self.config.distillation_min_confidence:
            return

        raw_units = args.get("units") or []
        if not isinstance(raw_units, list):
            return

        has_pitfall = any(u.get("kind") == "pitfall" for u in raw_units if isinstance(u, dict))
        if outcome == "failure" and not has_pitfall:
            return

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for raw in raw_units:
            if not isinstance(raw, dict):
                continue
            kind = raw.get("kind", "strategy")
            if kind == "pitfall" and confidence < 0.4:
                continue
            unit = ReasoningUnit(
                id="",
                title=str(raw.get("title", ""))[:200],
                description=str(raw.get("description", ""))[:500],
                content=str(raw.get("content", ""))[:2000],
                kind=kind,
                domain=str(raw.get("domain", "general"))[:100],
                tools=[str(t) for t in (raw.get("tools") or [])][:10],
                confidence=confidence,
                source="distilled",
                created_at=now,
                # Written as pending — the async IndexWorker builds the embedding
                # + graph in the background so the user-facing turn never blocks.
                index_status="pending",
            )
            if not unit.title or not unit.content:
                continue
            saved = self.bank.add_unit(unit)
            self._enqueue(saved.id)
            logger.info("Distilled reasoning unit (pending index): {}", saved.title)

    def _enqueue(self, unit_id: str) -> None:
        """Fire-and-forget enqueue to the background indexer, if available."""
        worker = self.index_worker
        if worker is None or not unit_id:
            return
        try:
            worker.enqueue(unit_id)
        except Exception:
            logger.exception("Failed to enqueue unit {} for background indexing", unit_id)
