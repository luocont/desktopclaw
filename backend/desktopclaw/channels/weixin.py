"""WeChat channel via Node.js iLink Bot bridge."""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from loguru import logger

from desktopclaw.bus.events import OutboundMessage
from desktopclaw.bus.queue import MessageBus
from desktopclaw.channels.base import BaseChannel
from desktopclaw.config.schema import WeixinConfig

WS_RECONNECT_DELAY = 5.0
BRIDGE_STARTUP_DELAY = 2.0


def _find_bridge_dir() -> Path | None:
    start = Path(__file__).resolve()
    for parent in [start.parent, *start.parents]:
        candidate = parent / "bridge" / "weixin"
        if candidate.exists() and (candidate / "index.js").exists():
            return candidate
    return None


class WeixinChannel(BaseChannel):
    name = "weixin"
    display_name = "WeChat"

    def __init__(self, config: WeixinConfig, bus: MessageBus):
        super().__init__(config, bus)
        self.config: WeixinConfig = config
        self._ws: Any = None
        self._ws_task: asyncio.Task | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._account_context_tokens: dict[str, dict[str, str]] = {}
        self._bridge_process: subprocess.Popen | None = None

    async def start(self) -> None:
        self._running = True
        self._loop = asyncio.get_running_loop()

        await self._start_bridge()

        logger.info("WeChat bridge connecting to ws://localhost:{}", self.config.bridge_port)
        await self._ws_loop()

    async def stop(self) -> None:
        self._running = False
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._stop_bridge()
        logger.info("WeChat channel stopped")

    async def send(self, msg: OutboundMessage) -> None:
        if self._ws is None:
            logger.warning("WeChat: no bridge connection, dropping outbound message")
            return

        metadata = msg.metadata or {}
        account_id = metadata.get("weixin_account_id", "")
        to_user_id = metadata.get("weixin_from_user_id", "")
        context_token = metadata.get("weixin_context_token", "")

        if not account_id or not to_user_id:
            logger.warning("WeChat: missing account_id or to_user_id in metadata, dropping message")
            return

        payload = {
            "type": "outbound",
            "accountId": account_id,
            "toUserId": to_user_id,
            "contextToken": context_token,
            "text": msg.content,
        }

        try:
            await self._ws.send(json.dumps(payload))
            logger.debug("WeChat: sent to {}: {}", to_user_id, msg.content[:50])
        except Exception as e:
            logger.error("WeChat: send failed: {}", e)

    async def _start_bridge(self) -> None:
        bridge_dir = _find_bridge_dir()
        if bridge_dir is None:
            logger.error("WeChat: bridge directory not found")
            return

        node_exe = shutil.which("node")
        if node_exe is None:
            logger.error("WeChat: Node.js not found. Please install Node.js >= 20")
            return

        node_modules = bridge_dir / "node_modules"
        if not node_modules.exists():
            logger.info("WeChat: installing bridge dependencies...")
            try:
                subprocess.run(
                    ["npm", "install"],
                    cwd=bridge_dir,
                    check=True,
                    capture_output=True,
                )
            except subprocess.CalledProcessError as e:
                logger.error("WeChat: npm install failed: {}", e.stderr.decode() if e.stderr else str(e))
                return

        env = dict(subprocess.os.environ)
        env["WEIXIN_BRIDGE_PORT"] = str(self.config.bridge_port)

        logger.info("WeChat: starting bridge on port {}", self.config.bridge_port)
        self._bridge_process = subprocess.Popen(
            ["node", "index.js"],
            cwd=bridge_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

        await asyncio.sleep(BRIDGE_STARTUP_DELAY)

        if self._bridge_process.poll() is not None:
            stderr = self._bridge_process.stderr.read().decode() if self._bridge_process.stderr else ""
            logger.error("WeChat: bridge process exited immediately: {}", stderr)
            self._bridge_process = None
            return

        logger.info("WeChat: bridge process started (pid={})", self._bridge_process.pid)

    def _stop_bridge(self) -> None:
        if self._bridge_process is not None:
            logger.info("WeChat: stopping bridge process (pid={})", self._bridge_process.pid)
            self._bridge_process.terminate()
            try:
                self._bridge_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._bridge_process.kill()
            self._bridge_process = None

    async def _ws_loop(self) -> None:
        try:
            import websockets
        except ImportError:
            logger.error("WeChat: websockets package not installed. Run: pip install websockets")
            return

        while self._running:
            try:
                uri = f"ws://localhost:{self.config.bridge_port}"
                logger.info("WeChat: connecting to {}", uri)
                async with websockets.connect(uri) as ws:
                    self._ws = ws
                    logger.info("WeChat: bridge connected")
                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            event = json.loads(raw)
                            await self._on_bridge_event(event)
                        except Exception as e:
                            logger.warning("WeChat: error processing event: {}", e)
            except Exception as e:
                if not self._running:
                    break
                logger.warning("WeChat: bridge disconnected: {}. Reconnecting in {}s...", e, WS_RECONNECT_DELAY)
                self._ws = None
                await asyncio.sleep(WS_RECONNECT_DELAY)

        self._ws = None

    async def _on_bridge_event(self, event: dict) -> None:
        if event.get("type") != "inbound":
            return

        account_id = event.get("accountId", "")
        from_user_id = event.get("fromUserId", "")
        context_token = event.get("contextToken", "")
        text = event.get("text", "").strip()

        if not from_user_id:
            return

        if not text:
            logger.debug("WeChat: empty text from {}, skipping", from_user_id)
            return

        logger.info("WeChat: inbound from {}: {}", from_user_id, text[:80])

        await self._handle_message(
            sender_id=from_user_id,
            chat_id=from_user_id,
            content=text,
            metadata={
                "weixin_account_id": account_id,
                "weixin_from_user_id": from_user_id,
                "weixin_context_token": context_token,
            },
        )
