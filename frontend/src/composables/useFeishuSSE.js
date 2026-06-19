/**
 * Feishu SSE composable — connects to /feishu/events (via api.feishu) and
 * drives chat.appendUser + chat.sendToAi when a text message arrives.
 *
 * Maintains a small LRU set of seen msgIds so duplicates from the SSE
 * heartbeat / re-delivery don't trigger duplicate AI calls.
 */

import { ref } from 'vue'
import { connectFeishuEvents } from '../api/feishu.js'
import { useChat } from '../stores/useChat.js'
import { useReminder } from '../stores/useReminder.js'

const MAX_SEEN = 1000

export function useFeishuSSE() {
  const connected = ref(false)
  const lastError = ref('')
  let disconnect = null
  const seen = new Set()
  const chat = useChat()
  const reminder = useReminder()

  function rememberMsgId(id) {
    if (!id) return false
    if (seen.has(id)) return true
    seen.add(id)
    if (seen.size > MAX_SEEN) {
      const first = seen.values().next().value
      seen.delete(first)
    }
    return false
  }

  async function start() {
    const maxAttempts = 15
    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      try {
        disconnect = await connectFeishuEvents(handleEvent)
        connected.value = true
        lastError.value = ''
        return
      } catch (err) {
        if (attempt < maxAttempts) {
          await new Promise((r) => setTimeout(r, 2000))
          continue
        }
        console.error('飞书 SSE 连接失败:', err)
        connected.value = false
        lastError.value = err?.message || String(err)
        reminder.show('飞书消息通道未连接，目前仅能本地聊天')
      }
    }
  }

  function stop() {
    try { disconnect?.() } catch (e) { console.warn('飞书 SSE 断开失败:', e) }
    disconnect = null
    connected.value = false
  }

  async function handleEvent(data) {
    if (!data) return
    if (data.type === 'heartbeat' || data.type === 'error') return
    if (rememberMsgId(data.msgId)) return
    if (data.msgType === 'text' && data.content) {
      chat.appendUser(data.content)
      await chat.scrollToBottom()
      await chat.sendToAi(data.content)
    }
  }

  return { connected, lastError, start, stop }
}
