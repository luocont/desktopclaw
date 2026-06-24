/**
 * Map backend session messages to frontend UI shape and merge helpers.
 */

function normalizeUiMessage(msg) {
  if (!msg) return null
  const role = msg.role
  if (role === 'system') return null

  if (msg.blockType) {
    const out = {
      role: role === 'assistant' ? 'ai' : role,
      blockType: msg.blockType,
      content: msg.content || '',
      collapsed: msg.collapsed !== false,
    }
    if (msg.meta) out.meta = msg.meta
    if (msg.usage) out.usage = msg.usage
    if (msg.isError) out.isError = true
    return out
  }

  if (role === 'assistant' || role === 'ai') {
    if (msg.isToolCall || msg.tool_calls) {
      const name = msg.meta?.name || msg.name || 'tool'
      return {
        role: 'ai',
        blockType: name === 'spawn' ? 'subagent' : 'tool',
        content: msg.content || 'tool call',
        collapsed: true,
        meta: msg.meta || { name },
      }
    }
    if (msg.isThinking) {
      return {
        role: 'ai',
        blockType: 'thinking',
        content: msg.content || '',
        collapsed: true,
      }
    }
    const content = String(msg.content || '').trim()
    if (!content) return null
    return { role: 'ai', blockType: 'reply', content: msg.content, usage: msg.usage || null }
  }

  if (role === 'tool') {
    const name = msg.name || 'tool'
    return {
      role: 'ai',
      blockType: name === 'spawn' ? 'subagent' : 'tool',
      content: msg.content || name,
      collapsed: true,
      meta: { name, result: msg.content || '' },
    }
  }

  if (role === 'user') {
    const content = String(msg.content || '').trim()
    if (!content && !msg.audioPath) return null
    const out = { role: 'user', content: msg.content || '' }
    if (msg.audioPath) out.audioPath = msg.audioPath
    return out
  }

  return null
}

export function backendToUi(msg) {
  return normalizeUiMessage(msg)
}

export function backendMessagesToUi(messages) {
  if (!Array.isArray(messages)) return []
  return messages.map(backendToUi).filter(Boolean)
}

export function messageDedupeKey(msg) {
  const role = msg.role || ''
  const blockType = msg.blockType || ''
  const content = String(msg.content || '').slice(0, 200)
  const flags = [
    blockType,
    msg.isToolCall ? 'tool' : '',
    msg.isThinking ? 'think' : '',
    msg.audioPath || '',
    msg.meta?.name || '',
  ].join('|')
  return `${role}:${flags}:${content}`
}

export function mergeMessages(localMessages, remoteMessages) {
  const merged = []
  const seen = new Set()

  for (const msg of [...(localMessages || []), ...(remoteMessages || [])]) {
    const key = messageDedupeKey(msg)
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(msg)
  }
  return merged
}

export function pickRicherMessages(a, b) {
  const listA = Array.isArray(a) ? a : []
  const listB = Array.isArray(b) ? b : []
  if (listB.length > listA.length) return listB
  if (listA.length > listB.length) return listA
  return mergeMessages(listA, listB)
}
