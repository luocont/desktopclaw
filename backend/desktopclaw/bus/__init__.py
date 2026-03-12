"""Message bus module for decoupled channel-agent communication."""

from desktopclaw.bus.events import InboundMessage, OutboundMessage
from desktopclaw.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
