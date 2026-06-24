/**
 * Chat API — wraps POST /chat in both standard (JSON) and streaming (SSE)
 * modes. The backend supports both via the `Accept` header (see
 * `_handle_chat_request` in api/server.py).
 *
 * The Electron renderer can call these directly. The legacy
 * `window.electronAPI.sendMessage` IPC path (which proxies a non-streaming
 * POST through the main process) is kept available but is no longer the
 * primary path — see `api/index.js` for the chosen route.
 */

import request from './request.js'
import { streamPost } from './stream.js'

/**
 * @typedef {Object} ChatOptions
 * @property {string} [modelId]
 * @property {string} [apiKey]
 * @property {string} [baseUrl]
 * @property {string} [personality]
 * @property {string} [customPrompt]
 * @property {string} [channel]
 */

/**
 * Standard non-streaming chat — single round-trip JSON.
 * @param {string} message
 * @param {ChatOptions} [options]
 * @param {AbortSignal} [signal]
 * @returns {Promise<{success: boolean, response?: string, error?: string}>}
 */
export async function sendMessage(message, options = {}, signal) {
  const body = buildChatBody(message, options)
  // We intentionally don't use postJson here — postJson throws on
  // {success:false}, but the caller wants to surface the raw envelope so it
  // can render `data.error` inside the chat bubble.
  const { data } = await request.post('/chat', body, { signal })
  return data
}

/**
 * Streaming chat — invokes `onEvent` for every SSE frame
 * (`thinking | progress | tool_call | complete`).
 * @param {string} message
 * @param {ChatOptions} options
 * @param {(event: import('./stream.js').SseEvent) => void} onEvent
 * @param {AbortSignal} [signal]
 */
export async function streamMessage(message, options, onEvent, signal) {
  const body = buildChatBody(message, options)
  await streamPost({
    path: '/chat',
    body,
    onEvent,
    signal,
    apiKey: options?.apiKey,
  })
}

function buildChatBody(message, options = {}) {
  const out = { message }
  if (options.channel) out.channel = options.channel
  if (options.modelId) out.modelId = options.modelId
  if (options.apiKey) out.apiKey = options.apiKey
  if (options.baseUrl) out.baseUrl = options.baseUrl
  if (options.personality) out.personality = options.personality
  if (options.customPrompt) out.customPrompt = options.customPrompt
  if (options.sessionKey) out.sessionKey = options.sessionKey
  return out
}
