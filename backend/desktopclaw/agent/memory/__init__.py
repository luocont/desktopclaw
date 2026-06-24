"""Agent memory system: user facts + reasoning strategies."""

from desktopclaw.utils.helpers import estimate_message_tokens

from desktopclaw.agent.memory.consolidator import MemoryConsolidator
from desktopclaw.agent.memory.distiller import StrategyDistiller
from desktopclaw.agent.memory.embedder import LocalEmbedder
from desktopclaw.agent.memory.factory import AgentMemoryServices, build_memory_services
from desktopclaw.agent.memory.graph import MemoryGraphStore
from desktopclaw.agent.memory.graph_builder import GraphBuilder
from desktopclaw.agent.memory.index_worker import MemoryIndexWorker
from desktopclaw.agent.memory.injector import format_strategies, inject_into_system_prompt
from desktopclaw.agent.memory.reasoning_bank import ReasoningBankStore
from desktopclaw.agent.memory.retriever import MRAgentRetriever
from desktopclaw.agent.memory.store import MemoryStore
from desktopclaw.agent.memory.triggers import TriggerState
from desktopclaw.agent.memory.types import ReasoningUnit, RetrievalResult, TriggerLevel

__all__ = [
    "AgentMemoryServices",
    "GraphBuilder",
    "LocalEmbedder",
    "MemoryGraphStore",
    "MemoryIndexWorker",
    "MemoryStore",
    "MRAgentRetriever",
    "MemoryConsolidator",
    "ReasoningBankStore",
    "ReasoningUnit",
    "RetrievalResult",
    "StrategyDistiller",
    "TriggerLevel",
    "TriggerState",
    "build_memory_services",
    "estimate_message_tokens",
    "format_strategies",
    "inject_into_system_prompt",
]
