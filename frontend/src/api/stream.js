/**
 * SSE client for POST endpoints.
 *
 * `EventSource` only supports GET, but the backend's `POST /chat` accepts an
 * `Accept: text/event-stream` header to upgrade the standard JSON response
 * into an SSE stream that emits `thinking`, `progress`, `tool_call`, and
 * `complete` events (see `backend/desktopclaw/api/server.py:_send_streaming_response`).
 *
 * This module reads the response body via `fetch` + `ReadableStream`, parses
 * the `data: <json>\n\n` framing inline, and dispatches each event to
 * `onEvent`. It does NOT depend on axios because axios in browsers buffers
 * the full body before resolving — defeating streaming.
 */

import { getBaseUrl } from './config.js'

/**
 * @typedef {Object} SseEvent
 * @property {'thinking' | 'progress' | 'tool_call' | 'complete' | string} type
 * @property {string} [content]
 * @property {string} [response]
 */

/**
 * @typedef {Object} StreamPostOptions
 * @property {string} path                   - e.g. "/chat"
 * @property {object} body                   - JSON body to send
 * @property {(event: SseEvent) => void} onEvent
 * @property {AbortSignal} [signal]
 * @property {string} [apiKey]               - Optional Bearer key
 */

/**
 * POST a JSON body and consume the response as an SSE stream.
 *
 * Resolves once the stream ends. Rejects on network errors, non-2xx HTTP
 * status, or aborts. The caller is responsible for translating the final
 * `complete` event into application state.
 *
 * @param {StreamPostOptions} opts
 * @returns {Promise<void>}
 */
export async function streamPost({ path, body, onEvent, signal, apiKey }) {
  const url = `${getBaseUrl()}${path}`
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  }
  if (apiKey) headers.Authorization = `Bearer ${apiKey}`

  const response = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
    signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${response.statusText}`)
  }
  if (!response.body) {
    throw new Error('Response has no readable body (streaming unsupported)')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  try {
    // Loop until the server closes the stream. Each SSE event is delimited
    // by a blank line (\n\n); within an event, data may span multiple
    // `data:` prefixed lines that we concatenate per the spec.
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let sep
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        const event = parseSseFrame(raw)
        if (event) {
          try {
            onEvent(event)
          } catch (e) {
            // A handler crash should not poison the stream.
            console.error('[stream] onEvent handler threw:', e)
          }
        }
      }
    }
  } finally {
    try { reader.releaseLock() } catch { /* noop */ }
  }
}

/**
 * Parse an SSE frame (one or more `field: value` lines) into a JSON event.
 * Returns null for keep-alive comments / unparseable frames.
 * @param {string} frame
 * @returns {SseEvent | null}
 */
function parseSseFrame(frame) {
  const dataLines = []
  for (const line of frame.split('\n')) {
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).replace(/^ /, ''))
    }
    // Other fields (event:, id:, retry:) are ignored — backend doesn't use them.
  }
  if (dataLines.length === 0) return null
  const payload = dataLines.join('\n')
  try {
    return JSON.parse(payload)
  } catch {
    return null
  }
}
