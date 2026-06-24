/**
 * Conversation store — unified chat history for pet + chat UIs.
 * Persists to localStorage and syncs via Electron IPC chat-state hub.
 */

import { ref, computed } from 'vue'
import { STORAGE_KEYS } from '../utils/constants.js'
import { fetchSessions, fetchSessionMessages, deleteSession } from '../api/sessions.js'
import { backendMessagesToUi, mergeMessages, pickRicherMessages } from '../utils/messageMapper.js'
import { callElectronApi, hasElectronApi } from '../utils/electronBridge.js'

const DEFAULT_SESSION_KEY = 'api:frontend:api'
const LEGACY_SESSION_KEYS = ['api:frontend', 'api:frontend:api']

const conversations = ref([])
const activeId = ref(null)

function readLs(key, fallback = null) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function writeLs(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* ignore */
  }
}

function isMigrated() {
  try {
    return localStorage.getItem(STORAGE_KEYS.historyMigrated) === '1'
  } catch {
    return false
  }
}

function markMigrated() {
  try {
    localStorage.setItem(STORAGE_KEYS.historyMigrated, '1')
  } catch {
    /* ignore */
  }
}

function persist() {
  writeLs(STORAGE_KEYS.conversations, conversations.value)
  if (activeId.value) {
    localStorage.setItem(STORAGE_KEYS.activeConversationId, activeId.value)
  } else {
    localStorage.removeItem(STORAGE_KEYS.activeConversationId)
  }
}

function loadFromStorage() {
  const stored = readLs(STORAGE_KEYS.conversations, [])
  conversations.value = Array.isArray(stored) ? stored.map(normalizeConversation) : []
  const savedActive = localStorage.getItem(STORAGE_KEYS.activeConversationId)
  if (savedActive && conversations.value.some((c) => c.id === savedActive)) {
    activeId.value = savedActive
  } else if (conversations.value.length > 0) {
    activeId.value = sortedList.value[0]?.id || null
  }
}

function normalizeConversation(conv) {
  return {
    id: conv.id,
    title: conv.title || '新对话',
    updatedAt: conv.updatedAt || Date.now(),
    sessionKey: conv.sessionKey || DEFAULT_SESSION_KEY,
    messages: Array.isArray(conv.messages) ? conv.messages : [],
    backendSyncedAt: conv.backendSyncedAt || null,
  }
}

function generateId() {
  return `conv_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`
}

function deriveTitle(messages) {
  const firstUser = messages.find((m) => m.role === 'user' && m.content)
  if (firstUser) {
    const text = String(firstUser.content).trim()
    return text.length > 20 ? `${text.slice(0, 20)}…` : text
  }
  return '新对话'
}

function buildSnapshot() {
  return {
    activeId: activeId.value,
    conversations: JSON.parse(JSON.stringify(conversations.value)),
    updatedAt: Date.now(),
  }
}

const sortedList = computed(() =>
  [...conversations.value].sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0)),
)

const activeConversation = computed(() =>
  conversations.value.find((c) => c.id === activeId.value) || null,
)

function findBySessionKey(sessionKey) {
  return conversations.value.find((c) => c.sessionKey === sessionKey)
}

function createNew(options = {}) {
  const id = options.id || generateId()
  const conv = {
    id,
    title: options.title || '新对话',
    updatedAt: Date.now(),
    sessionKey: options.sessionKey || `api:frontend:${id}`,
    messages: options.messages ? [...options.messages] : [],
    backendSyncedAt: options.backendSyncedAt || null,
  }
  conversations.value.unshift(conv)
  activeId.value = conv.id
  persist()
  syncSnapshot()
  return conv
}

function ensureActive() {
  if (!activeId.value || !conversations.value.some((c) => c.id === activeId.value)) {
    if (conversations.value.length === 0) {
      return createNew({ sessionKey: DEFAULT_SESSION_KEY, title: '主对话' })
    }
    activeId.value = sortedList.value[0].id
    persist()
  }
  return conversations.value.find((c) => c.id === activeId.value)
}

function switchTo(id) {
  if (!conversations.value.some((c) => c.id === id)) return null
  activeId.value = id
  persist()
  syncSnapshot()
  const conv = conversations.value.find((c) => c.id === id)
  return conv ? [...conv.messages] : []
}

function saveCurrent(messages) {
  const conv = ensureActive()
  if (!conv) return
  const idx = conversations.value.findIndex((c) => c.id === conv.id)
  if (idx === -1) return

  const snapshot = JSON.parse(JSON.stringify(messages))
  const title = deriveTitle(snapshot)
  conversations.value[idx] = {
    ...conversations.value[idx],
    messages: snapshot,
    title,
    updatedAt: Date.now(),
  }
  persist()
}

async function remove(id) {
  const idx = conversations.value.findIndex((c) => c.id === id)
  if (idx === -1) return
  const conv = conversations.value[idx]
  if (conv?.sessionKey?.startsWith('api:frontend')) {
    try {
      await deleteSession(conv.sessionKey)
    } catch (err) {
      console.warn('[conversations] backend delete failed:', conv.sessionKey, err)
    }
  }
  conversations.value.splice(idx, 1)
  if (activeId.value === id) {
    activeId.value = conversations.value.length > 0 ? sortedList.value[0].id : null
  }
  persist()
  syncSnapshot()
}

function getActiveSessionKey() {
  const conv = activeConversation.value || ensureActive()
  return conv?.sessionKey || DEFAULT_SESSION_KEY
}

function hydrateActiveToChat() {
  const conv = ensureActive()
  return conv ? [...conv.messages] : []
}

function applyRemoteSnapshot(snapshot) {
  if (!snapshot || !Array.isArray(snapshot.conversations)) return false
  const remoteUpdated = snapshot.updatedAt || 0
  const localUpdated = Math.max(0, ...conversations.value.map((c) => c.updatedAt || 0))

  if (remoteUpdated <= localUpdated && conversations.value.length > 0) {
    return false
  }

  conversations.value = snapshot.conversations.map(normalizeConversation)
  if (snapshot.activeId && conversations.value.some((c) => c.id === snapshot.activeId)) {
    activeId.value = snapshot.activeId
  } else if (conversations.value.length > 0) {
    activeId.value = sortedList.value[0].id
  }
  persist()
  return true
}

async function loadRemoteSnapshot() {
  if (!hasElectronApi('getChatState')) return false
  try {
    const snapshot = await callElectronApi('getChatState')
    if (snapshot) {
      return applyRemoteSnapshot(snapshot)
    }
  } catch {
    /* ignore */
  }
  return false
}

function syncSnapshot() {
  const snapshot = buildSnapshot()
  persist()
  if (hasElectronApi('syncChatState')) {
    callElectronApi('syncChatState', snapshot)
  }
}

async function upsertFromBackendSession(sessionKey, backendMessages, updatedAtIso) {
  const uiMessages = backendMessagesToUi(backendMessages)
  const backendUpdated = updatedAtIso ? Date.parse(updatedAtIso) || Date.now() : Date.now()
  let conv = findBySessionKey(sessionKey)

  if (!conv && LEGACY_SESSION_KEYS.includes(sessionKey)) {
    conv = conversations.value.find((c) => LEGACY_SESSION_KEYS.includes(c.sessionKey))
  }

  if (conv) {
    const idx = conversations.value.findIndex((c) => c.id === conv.id)
    const merged = pickRicherMessages(conv.messages, uiMessages)
    conversations.value[idx] = {
      ...conv,
      messages: mergeMessages(conv.messages, merged),
      updatedAt: Math.max(conv.updatedAt || 0, backendUpdated),
      backendSyncedAt: backendUpdated,
      title: deriveTitle(mergeMessages(conv.messages, merged)),
    }
  } else {
    const title = sessionKey === DEFAULT_SESSION_KEY || sessionKey === 'api:frontend'
      ? '主对话'
      : deriveTitle(uiMessages) || '新对话'
    createNew({
      sessionKey,
      title,
      messages: uiMessages,
      backendSyncedAt: backendUpdated,
    })
  }
}

async function importFromBackend(force = false) {
  try {
    const { success, sessions } = await fetchSessions()
    if (!success || !Array.isArray(sessions)) return

    for (const info of sessions) {
      const key = info.key
      if (!key || !key.startsWith('api:frontend')) continue

      const existing = findBySessionKey(key)
      if (!force && existing?.backendSyncedAt) {
        const backendUpdated = Date.parse(info.updated_at || '') || 0
        if (backendUpdated <= existing.backendSyncedAt) continue
      }

      try {
        const payload = await fetchSessionMessages(key)
        if (payload.success && Array.isArray(payload.messages)) {
          await upsertFromBackendSession(key, payload.messages, payload.updated_at)
        }
      } catch (err) {
        console.warn('[conversations] failed to fetch session', key, err)
      }
    }

    if (conversations.value.length === 0) {
      createNew({ sessionKey: DEFAULT_SESSION_KEY, title: '主对话' })
    } else if (!activeId.value) {
      activeId.value = sortedList.value[0].id
      persist()
    }

    markMigrated()
    syncSnapshot()
  } catch (err) {
    console.warn('[conversations] importFromBackend failed:', err)
    if (conversations.value.length === 0) {
      createNew({ sessionKey: DEFAULT_SESSION_KEY, title: '主对话' })
    }
  }
}

async function initializeHistory() {
  loadFromStorage()
  await loadRemoteSnapshot()
  await importFromBackend(false)
  ensureActive()
  syncSnapshot()
  return hydrateActiveToChat()
}

loadFromStorage()

export function useConversations() {
  return {
    conversations,
    activeId,
    sortedList,
    activeConversation,
    createNew,
    ensureActive,
    switchTo,
    saveCurrent,
    remove,
    loadFromStorage,
    getActiveSessionKey,
    hydrateActiveToChat,
    importFromBackend,
    initializeHistory,
    syncSnapshot,
    applyRemoteSnapshot,
    buildSnapshot,
  }
}
