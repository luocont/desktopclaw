/**
 * Feishu SSE subscription — the backend pushes inbound/outbound Feishu
 * messages on GET /feishu/events. We prefer the Electron IPC bridge (which
 * runs the SSE client in the main process and forwards parsed events) and
 * fall back to a direct EventSource in browser/dev contexts.
 */

import { getBaseUrl } from './config.js'
import { hasElectronApi, getElectronApi } from '../utils/electronBridge.js'

/**
 * Connect to the Feishu event stream and dispatch each event to `onEvent`.
 * Returns a `disconnect()` function the caller invokes on unmount.
 *
 * The Electron path forwards every `feishu-event` IPC message — payload
 * shape matches `data:` JSON emitted by the backend
 * (`{type: 'inbound'|'outbound'|'heartbeat', ...}`).
 *
 * @param {(event: object) => void} onEvent
 * @returns {Promise<() => void>}
 */
export async function connectFeishuEvents(onEvent) {
  if (hasElectronApi('connectFeishuSSE')) {
    const api = getElectronApi()
    api.removeFeishuListener?.()
    await api.connectFeishuSSE()
    api.onFeishuEvent((data) => onEvent(data))
    return () => {
      try { api.removeFeishuListener?.() } catch { /* noop */ }
      try { api.disconnectFeishuSSE?.() } catch { /* noop */ }
    }
  }

  // Browser fallback. EventSource lacks custom headers, so this path cannot
  // attach the API key — fine because /feishu/events doesn't require auth.
  const es = new EventSource(`${getBaseUrl()}/feishu/events`)
  es.onmessage = (e) => {
    try {
      onEvent(JSON.parse(e.data))
    } catch (err) {
      console.error('[feishu] failed to parse SSE frame:', err)
    }
  }
  es.onerror = () => {
    // EventSource auto-reconnects; surface the state so callers can update UI.
    onEvent({ type: 'error' })
  }
  return () => {
    try { es.close() } catch { /* noop */ }
  }
}
