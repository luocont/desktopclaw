import { getUpdates } from "./api.js";
import { loadSyncBuf, saveSyncBuf } from "./accounts.js";

const DEFAULT_LONG_POLL_TIMEOUT_MS = 35_000;
const MAX_CONSECUTIVE_FAILURES = 3;
const BACKOFF_DELAY_MS = 30_000;
const RETRY_DELAY_MS = 2_000;
const SESSION_EXPIRED_ERRCODE = -14;

function sleep(ms, signal) {
  return new Promise((resolve, reject) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener("abort", () => {
      clearTimeout(t);
      reject(new Error("aborted"));
    }, { once: true });
  });
}

export async function monitorWeixin({ accountId, baseUrl, token, onMessage, abortSignal, longPollTimeoutMs }) {
  console.log(`[Weixin] Monitor started: accountId=${accountId} baseUrl=${baseUrl}`);

  let getUpdatesBuf = loadSyncBuf(accountId);
  if (getUpdatesBuf) {
    console.log(`[Weixin] Resuming from previous sync buf`);
  }

  let nextTimeoutMs = longPollTimeoutMs ?? DEFAULT_LONG_POLL_TIMEOUT_MS;
  let consecutiveFailures = 0;
  let sessionPausedUntil = 0;

  while (!abortSignal?.aborted) {
    try {
      if (Date.now() < sessionPausedUntil) {
        const remaining = sessionPausedUntil - Date.now();
        console.log(`[Weixin] Session paused, waiting ${Math.ceil(remaining / 60_000)} min...`);
        await sleep(Math.min(remaining, 60_000), abortSignal);
        continue;
      }

      const resp = await getUpdates({
        baseUrl,
        token,
        get_updates_buf: getUpdatesBuf,
        timeoutMs: nextTimeoutMs,
      });

      if (resp.longpolling_timeout_ms != null && resp.longpolling_timeout_ms > 0) {
        nextTimeoutMs = resp.longpolling_timeout_ms;
      }

      const isApiError =
        (resp.ret !== undefined && resp.ret !== 0) ||
        (resp.errcode !== undefined && resp.errcode !== 0);

      if (isApiError) {
        const isSessionExpired =
          resp.errcode === SESSION_EXPIRED_ERRCODE || resp.ret === SESSION_EXPIRED_ERRCODE;

        if (isSessionExpired) {
          const pauseMs = 60 * 60 * 1000;
          sessionPausedUntil = Date.now() + pauseMs;
          console.error(`[Weixin] Session expired, pausing for 1 hour`);
          consecutiveFailures = 0;
          await sleep(pauseMs, abortSignal);
          continue;
        }

        consecutiveFailures++;
        console.error(`[Weixin] getUpdates failed: ret=${resp.ret} errcode=${resp.errcode} (${consecutiveFailures}/${MAX_CONSECUTIVE_FAILURES})`);

        if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
          consecutiveFailures = 0;
          await sleep(BACKOFF_DELAY_MS, abortSignal);
        } else {
          await sleep(RETRY_DELAY_MS, abortSignal);
        }
        continue;
      }

      consecutiveFailures = 0;

      if (resp.get_updates_buf != null && resp.get_updates_buf !== "") {
        saveSyncBuf(accountId, resp.get_updates_buf);
        getUpdatesBuf = resp.get_updates_buf;
      }

      const msgs = resp.msgs ?? [];
      for (const msg of msgs) {
        const fromUserId = msg.from_user_id ?? "";
        const contextToken = msg.context_token ?? "";

        const textItems = (msg.item_list ?? []).filter((i) => i.type === 1);
        const text = textItems.map((i) => i.text_item?.text ?? "").join("").trim();

        const mediaItems = (msg.item_list ?? []).filter((i) => [2, 3, 4, 5].includes(i.type));

        console.log(`[Weixin] Inbound: from=${fromUserId} text="${text.slice(0, 50)}" mediaCount=${mediaItems.length}`);

        onMessage({
          fromUserId,
          contextToken,
          text,
          mediaItems,
          rawMsg: msg,
          accountId,
        });
      }

    } catch (err) {
      if (abortSignal?.aborted) {
        console.log("[Weixin] Monitor stopped");
        return;
      }
      consecutiveFailures++;
      console.error(`[Weixin] getUpdates error (${consecutiveFailures}/${MAX_CONSECUTIVE_FAILURES}): ${String(err)}`);
      if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
        consecutiveFailures = 0;
        await sleep(BACKOFF_DELAY_MS, abortSignal);
      } else {
        await sleep(RETRY_DELAY_MS, abortSignal);
      }
    }
  }

  console.log("[Weixin] Monitor ended");
}
