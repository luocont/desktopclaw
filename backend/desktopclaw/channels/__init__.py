"""Chat channels module with plugin architecture."""

from desktopclaw.channels.base import BaseChannel
from desktopclaw.channels.manager import ChannelManager

__all__ = ["BaseChannel", "ChannelManager"]
