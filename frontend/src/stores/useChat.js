/**
 * Chat store — owns the message list and the streaming send pipeline.
 *
 * Streaming flow (via /chat with Accept: text/event-stream):
 *   - 'thinking'  → ensure a placeholder message with isThinking=true exists
 *   - 'progress'  → append/update progress text on that placeholder
 *   - 'tool_call' → push a separate {isToolCall: true} message
 *   - 'complete'  → replace the placeholder with the final response text
 *
 * Non-streaming fallback uses sendMessage() and replaces the thinking
 * placeholder when the JSON body arrives.
 */

import { ref, nextTick } from 'vue'
import { sendMessage as apiSendMessage, streamMessage as apiStreamMessage } from '../api/chat.js'
import { useSettings } from './useSettings.js'

const messages = ref([])
const inputValue = ref('')
const loading = ref(false)
const messagesRef = ref(null)
const lastError = ref('')

// Track in-flight stream so we can cancel on unmount / new send.
let _abortController = null

function pushUser(content) {
  messages.value.push({ role: 'user', content })
}

/**
 * Insert a thinking placeholder and return its index so we can update it.
 */
function pushThinking(text = '思考中...') {
  messages.value.push({ role: 'ai', content: text, isThinking: true })
  return messages.value.length - 1
}

/**
 * Replace the first thinking placeholder with `replacement` (or remove if
 * replacement is null). Centralized so we no longer duplicate this logic
 * in three places like App.vue did.
 */
function resolveThinking(replacement = null) {
  const idx = messages.value.findIndex((m) => m.isThinking)
  if (idx === -1) return
  if (replacement) {
    messages.value.splice(idx, 1, replacement)
  } else {
    messages.value.splice(idx, 1)
  }
}

async function scrollToBottom() {
  await nextTick()
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

/**
 * Send a message and stream the response. When streaming fails (e.g. the
 * backend is unreachable, or running through a transport that does not
 * support fetch streams), fall back to the JSON path.
 *
 * @param {string} text
 */
async function send(text) {
  const message = (text ?? inputValue.value).trim()
  if (!message || loading.value) return
  pushUser(message)
  inputValue.value = ''
  await scrollToBottom()
  await sendToAi(message)
}

/**
 * Kick off the AI call without first pushing a user bubble — used by Feishu
 * inbound where the upstream channel already populated the user message.
 */
async function sendToAi(message) {
  loading.value = true
  lastError.value = ''
  pushThinking('思考中...')
  await scrollToBottom()

  const settings = useSettings()
  const options = settings.chatOptions.value

  // Cancel any prior stream — only one chat in flight at a time.
  _abortController?.abort()
  _abortController = new AbortController()

  let receivedFinal = false
  try {
    await apiStreamMessage(
      message,
      options,
      (event) => {
        if (event.type === 'thinking') {
          // Already have a thinking placeholder; just refresh its text.
          const idx = messages.value.findIndex((m) => m.isThinking)
          if (idx !== -1) messages.value[idx].content = event.content || '思考中...'
        } else if (event.type === 'progress') {
          // Update the thinking placeholder with the latest progress line.
          const idx = messages.value.findIndex((m) => m.isThinking)
          if (idx !== -1) messages.value[idx].content = event.content || '...'
        } else if (event.type === 'tool_call') {
          // Insert a tool-call marker just before the thinking placeholder.
          const idx = messages.value.findIndex((m) => m.isThinking)
          const item = { role: 'ai', content: event.content || '', isToolCall: true }
          if (idx === -1) messages.value.push(item)
          else messages.value.splice(idx, 0, item)
        } else if (event.type === 'complete') {
          receivedFinal = true
          resolveThinking({ role: 'ai', content: event.response || '' })
        }
        scrollToBottom()
      },
      _abortController.signal,
    )

    // Some backend versions might end the stream without a complete event —
    // guard by falling back if no final body arrived.
    if (!receivedFinal) {
      throw new Error('streaming ended without a complete event')
    }
  } catch (err) {
    if (err?.name === 'AbortError') {
      resolveThinking({ role: 'ai', content: '请求已取消。' })
      return
    }
    console.warn('[chat] streaming failed, falling back to JSON:', err)
    try {
      // Bug #23: previously the fallback request ignored the abort signal,
      // so chat.abort() left a runaway JSON request alive. Thread the
      // controller's signal through.
      const data = await apiSendMessage(message, options, _abortController?.signal)
      if (data?.success) {
        resolveThinking({ role: 'ai', content: data.response })
      } else {
        resolveThinking({
          role: 'ai',
          content: '抱歉，处理消息时出现错误: ' + (data?.error || '未知错误'),
        })
      }
    } catch (fallbackErr) {
      if (fallbackErr?.name === 'AbortError' || fallbackErr?.code === 'ERR_CANCELED') {
        resolveThinking({ role: 'ai', content: '请求已取消。' })
        return
      }
      lastError.value = fallbackErr?.message || String(fallbackErr)
      resolveThinking({ role: 'ai', content: '连接失败: ' + lastError.value })
    }
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

/**
 * Push a finished assistant message directly (e.g. from voice upload result
 * which already has the agent's reply baked in).
 */
function pushAssistant(content, extra = {}) {
  messages.value.push({ role: 'ai', content, ...extra })
}

/**
 * Insert a user message without invoking the AI — used when an external
 * channel (Feishu) delivers the user's text and we just need to display it
 * before calling sendToAi() ourselves.
 */
function appendUser(content) {
  pushUser(content)
}

function abort() {
  _abortController?.abort()
  _abortController = null
}

export function useChat() {
  return {
    // State
    messages,
    inputValue,
    loading,
    messagesRef,
    lastError,
    // Actions
    send,
    sendToAi,
    appendUser,
    pushAssistant,
    resolveThinking,
    scrollToBottom,
    abort,
  }
}
