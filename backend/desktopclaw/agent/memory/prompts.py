"""Shared prompt fragments for memory LLM calls."""

MEMORY_LANGUAGE_RULE = (
    "记忆库统一使用中文（简体）。"
    "写入 title、description、content、history_entry、memory_update 等字段时必须使用中文。"
)

STRATEGY_HINT_TAG = "[策略提示]"
