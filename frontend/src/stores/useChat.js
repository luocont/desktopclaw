/**
 * Chat store — owns the message list and the streaming send pipeline.
 *
 * Streaming flow (via /chat with Accept: text/event-stream):
 *   - 'thinking'  → ensure a placeholder message with isThinking=true exists
 *   - 'progress'  → append/update progress text on that placeholder
 *   - 'tool_call' → push a collapsible tool/subagent block before the placeholder
 *   - 'complete'  → apply blocks snapshot (if any), then push final reply
 *
 * Non-streaming fallback uses sendMessage() and appends the reply after
 * finalizing any thinking placeholder.
 */

import { ref, nextTick } from 'vue'
import { sendMessage as apiSendMessage, streamMessage as apiStreamMessage } from '../api/chat.js'
import { useSettings } from './useSettings.js'
import { useConversations } from './useConversations.js'
import { formatLlmError } from '../utils/llmError.js'

const messages = ref([])
const inputValue = ref('')
const loading = ref(false)
const messagesRef = ref(null)
const lastError = ref('')

let _abortController = null

function pushUser(content) {
  messages.value.push({ role: 'user', content })
}

function pushThinking(text = '思考中...') {
  messages.value.push({ role: 'ai', content: text, isThinking: true })
  return messages.value.length - 1
}

function removeThinkingPlaceholder() {
  const idx = messages.value.findIndex((m) => m.isThinking)
  if (idx !== -1) messages.value.splice(idx, 1)
}

function finalizeThinkingBlock() {
  const idx = messages.value.findIndex((m) => m.isThinking)
  if (idx === -1) return
  const content = String(messages.value[idx].content || '').trim()
  const generic = ['思考中...', 'AI 正在思考...', '...']
  if (content && !generic.includes(content)) {
    messages.value[idx] = {
      role: 'ai',
      blockType: 'thinking',
      content,
      collapsed: true,
    }
  } else {
    messages.value.splice(idx, 1)
  }
}

function inferToolName(content, explicitName) {
  if (explicitName) return explicitName
  if (!content) return 'tool'
  const match = String(content).match(/^([a-zA-Z_][\w]*)\(/)
  return match ? match[1] : 'tool'
}

function insertToolBlock(event) {
  const name = inferToolName(event.content, event.name)
  const blockType = name === 'spawn' ? 'subagent' : 'tool'
  const meta = { name }
  if (event.args) meta.args = event.args
  if (event.label) meta.label = event.label
  const item = {
    role: 'ai',
    blockType,
    content: event.content || name,
    collapsed: true,
    meta,
  }
  const idx = messages.value.findIndex((m) => m.isThinking)
  if (idx === -1) messages.value.push(item)
  else messages.value.splice(idx, 0, item)
}

function findCurrentTurnStart() {
  for (let i = messages.value.length - 1; i >= 0; i -= 1) {
    if (messages.value[i].role === 'user') return i + 1
  }
  return 0
}

function applyTurnBlocks(blocks, usage) {
  if (!Array.isArray(blocks) || blocks.length === 0) return false
  const turnStart = findCurrentTurnStart()
  const prefix = messages.value.slice(0, turnStart)
  const mapped = blocks.map((block) => {
    const out = {
      ...block,
      role: block.role === 'assistant' ? 'ai' : (block.role || 'ai'),
      collapsed: block.collapsed !== false,
    }
    if (block.blockType === 'reply' && usage) out.usage = usage
    return out
  })
  messages.value = [...prefix, ...mapped]
  return true
}

function pushErrorReply(raw) {
  removeThinkingPlaceholder()
  messages.value.push({
    role: 'ai',
    content: formatLlmError(raw),
    isError: true,
  })
}

function completeSuccess(event) {
  if (!applyTurnBlocks(event.blocks, event.usage)) {
    finalizeThinkingBlock()
    messages.value.push({
      role: 'ai',
      blockType: 'reply',
      content: event.response || '',
      usage: event.usage || null,
    })
  }
}

/**
 * Replace the first thinking placeholder with `replacement` (or remove if null).
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

async function send(text) {
  const message = (text ?? inputValue.value).trim()
  if (!message || loading.value) return
  pushUser(message)
  inputValue.value = ''
  await scrollToBottom()
  await sendToAi(message)
}

async function sendToAi(message) {
  loading.value = true
  lastError.value = ''
  pushThinking('思考中...')
  await scrollToBottom()

  const settings = useSettings()
  const conversations = useConversations()
  const options = {
    ...settings.chatOptions.value,
    sessionKey: conversations.getActiveSessionKey(),
  }

  _abortController?.abort()
  _abortController = new AbortController()

  let receivedFinal = false
  try {
    await apiStreamMessage(
      message,
      options,
      (event) => {
        if (event.type === 'thinking') {
          const idx = messages.value.findIndex((m) => m.isThinking)
          if (idx !== -1) messages.value[idx].content = event.content || '思考中...'
        } else if (event.type === 'progress') {
          const idx = messages.value.findIndex((m) => m.isThinking)
          if (idx !== -1) messages.value[idx].content = event.content || '...'
        } else if (event.type === 'tool_call') {
          insertToolBlock(event)
        } else if (event.type === 'complete') {
          receivedFinal = true
          if (event.success === false || event.error) {
            const raw = event.error || event.response || '大模型连接失败'
            lastError.value = raw
            pushErrorReply(raw)
          } else {
            completeSuccess(event)
          }
        }
        scrollToBottom()
      },
      _abortController.signal,
    )

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
      const data = await apiSendMessage(message, options, _abortController?.signal)
      if (data?.success) {
        finalizeThinkingBlock()
        messages.value.push({
          role: 'ai',
          blockType: 'reply',
          content: data.response,
          usage: data.usage || null,
        })
      } else {
        const raw = data?.error || '未知错误'
        lastError.value = raw
        pushErrorReply(raw)
      }
    } catch (fallbackErr) {
      if (fallbackErr?.name === 'AbortError' || fallbackErr?.code === 'ERR_CANCELED') {
        resolveThinking({ role: 'ai', content: '请求已取消。' })
        return
      }
      lastError.value = fallbackErr?.message || String(fallbackErr)
      pushErrorReply(lastError.value)
    }
  } finally {
    loading.value = false
    conversations.saveCurrent(messages.value)
    conversations.syncSnapshot()
    await scrollToBottom()
  }
}

function pushAssistant(content, extra = {}) {
  messages.value.push({ role: 'ai', content, blockType: 'reply', ...extra })
}

function appendUser(content) {
  pushUser(content)
}

function abort() {
  _abortController?.abort()
  _abortController = null
}

export function useChat() {
  return {
    messages,
    inputValue,
    loading,
    messagesRef,
    lastError,
    send,
    sendToAi,
    appendUser,
    pushAssistant,
    resolveThinking,
    scrollToBottom,
    abort,
  }
}
