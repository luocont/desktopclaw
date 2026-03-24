import { WebSocketServer, WebSocket } from "ws";
import { listAccountIds, loadAccount } from "./accounts.js";
import { monitorWeixin } from "./monitor.js";
import { sendMessage } from "./api.js";
import { doQRLogin } from "./login.js";

const WS_PORT = parseInt(process.env.WEIXIN_BRIDGE_PORT ?? "3100", 10);
const RECONNECT_DELAY_MS = 5_000;

const isLoginMode = process.argv.includes("--login");

if (isLoginMode) {
  console.log("[Weixin] Login mode");
  doQRLogin().then((result) => {
    console.log(`[Weixin] Login successful: ${result.accountId}`);
    process.exit(0);
  }).catch((err) => {
    console.error(`[Weixin] Login failed: ${err.message}`);
    process.exit(1);
  });
} else {
  startBridge();
}

async function startBridge() {
  const accountIds = listAccountIds();
  if (accountIds.length === 0) {
    console.error("[Weixin] No accounts found. Run with --login first.");
    process.exit(1);
  }

  console.log(`[Weixin] Starting bridge on ws://localhost:${WS_PORT}`);
  console.log(`[Weixin] Accounts: ${accountIds.join(", ")}`);

  const wss = new WebSocketServer({ port: WS_PORT });
  const clients = new Set();

  wss.on("connection", (ws) => {
    console.log("[Weixin] Python backend connected");
    clients.add(ws);

    ws.on("message", async (data) => {
      try {
        const msg = JSON.parse(data.toString());
        await handleOutbound(msg);
      } catch (err) {
        console.error(`[Weixin] Error handling outbound: ${err.message}`);
      }
    });

    ws.on("close", () => {
      console.log("[Weixin] Python backend disconnected");
      clients.delete(ws);
    });

    ws.on("error", (err) => {
      console.error(`[Weixin] WebSocket error: ${err.message}`);
      clients.delete(ws);
    });
  });

  function broadcast(event) {
    const data = JSON.stringify(event);
    for (const client of clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(data);
      }
    }
  }

  const abortController = new AbortController();

  for (const accountId of accountIds) {
    const account = loadAccount(accountId);
    if (!account?.token) {
      console.warn(`[Weixin] Account ${accountId} has no token, skipping`);
      continue;
    }

    monitorWeixin({
      accountId,
      baseUrl: account.baseUrl ?? "https://ilinkai.weixin.qq.com",
      token: account.token,
      abortSignal: abortController.signal,
      onMessage: (msgData) => {
        broadcast({
          type: "inbound",
          accountId: msgData.accountId,
          fromUserId: msgData.fromUserId,
          contextToken: msgData.contextToken,
          text: msgData.text,
          mediaItems: msgData.mediaItems,
        });
      },
    }).catch((err) => {
      console.error(`[Weixin] Monitor error for ${accountId}: ${err.message}`);
    });
  }

  async function handleOutbound(msg) {
    if (msg.type !== "outbound") return;

    const accountId = msg.accountId;
    const account = loadAccount(accountId);
    if (!account?.token) {
      console.error(`[Weixin] No token for account ${accountId}`);
      return;
    }

    const baseUrl = account.baseUrl ?? "https://ilinkai.weixin.qq.com";
    const token = account.token;

    const itemList = [];

    if (msg.text) {
      itemList.push({
        type: 1,
        text_item: { text: msg.text },
      });
    }

    if (itemList.length === 0) return;

    try {
      await sendMessage({
        baseUrl,
        token,
        body: {
          msg: {
            to_user_id: msg.toUserId,
            context_token: msg.contextToken,
            item_list: itemList,
          },
        },
      });
      console.log(`[Weixin] Sent to ${msg.toUserId}: "${msg.text?.slice(0, 50)}"`);
    } catch (err) {
      console.error(`[Weixin] Send failed: ${err.message}`);
    }
  }

  process.on("SIGINT", () => {
    console.log("[Weixin] Shutting down...");
    abortController.abort();
    wss.close();
    process.exit(0);
  });

  process.on("SIGTERM", () => {
    abortController.abort();
    wss.close();
    process.exit(0);
  });

  console.log(`[Weixin] Bridge ready, waiting for Python backend connection...`);
}
