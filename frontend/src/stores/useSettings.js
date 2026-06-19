/**
 * Settings store — singleton composable that owns persona + provider config.
 *
 * Persistence layers (in order, both kept in sync):
 *   1. Backend `/settings` (authoritative across app restarts and across
 *      other channels like Feishu/CLI).
 *   2. localStorage (offline cache + survives across pages without a
 *      round-trip).
 *
 * The store registers an auth provider with the request layer at module
 * import so every request automatically gets the current Bearer key.
 */

import { ref, computed, reactive } from 'vue'
import { fetchSettings, saveSettings } from '../api/settings.js'
import { registerAuthProvider } from '../api/request.js'
import { DEFAULT_PERSONALITY } from '../data/personalities.js'
import { STORAGE_KEYS } from '../utils/constants.js'

function readLs(key, fallback = '') {
  try {
    return localStorage.getItem(key) || fallback
  } catch {
    return fallback
  }
}

function writeLs(key, value) {
  try {
    if (value) localStorage.setItem(key, value)
    else localStorage.removeItem(key)
  } catch {
    /* ignore */
  }
}

const baseUrl      = ref(readLs(STORAGE_KEYS.baseUrl))
const apiKey       = ref(readLs(STORAGE_KEYS.apiKey))
const modelId      = ref(readLs(STORAGE_KEYS.modelId))
const fastModelId  = ref(readLs(STORAGE_KEYS.fastModelId))
const personality  = ref(readLs(STORAGE_KEYS.personality, DEFAULT_PERSONALITY))
const birthday     = ref(readLs(STORAGE_KEYS.birthday))
const customPrompt = ref(readLs(STORAGE_KEYS.customPrompt))

const feishu = reactive({
  asrEnabled: true,
  ttsEnabled: true,
  ttsVoice: 'Cherry',
})

const lastSyncError = ref('')
const isSyncing = ref(false)

// Auth header: read from the live ref so updates take effect immediately.
registerAuthProvider(() => apiKey.value || null)

/**
 * Returns the request-time chat options derived from the current store
 * state — passed down to api.chat.streamMessage / sendMessage.
 */
const chatOptions = computed(() => ({
  modelId: modelId.value || undefined,
  apiKey: apiKey.value || undefined,
  baseUrl: baseUrl.value || undefined,
  personality: personality.value || undefined,
  customPrompt: customPrompt.value || undefined,
}))

function persistLocal() {
  writeLs(STORAGE_KEYS.apiKey, apiKey.value)
  writeLs(STORAGE_KEYS.baseUrl, baseUrl.value)
  writeLs(STORAGE_KEYS.modelId, modelId.value)
  writeLs(STORAGE_KEYS.fastModelId, fastModelId.value)
  writeLs(STORAGE_KEYS.personality, personality.value)
  writeLs(STORAGE_KEYS.birthday, birthday.value)
  writeLs(STORAGE_KEYS.customPrompt, customPrompt.value)
}

/**
 * Pull settings from the backend and overlay them onto the local store.
 * Backend wins on conflicts so a config.json edit on the server takes
 * effect, while localStorage acts as a warm cache.
 *
 * Bug #14: the previous implementation would overwrite a field whenever
 * the remote value was non-empty, even if the user had already started
 * typing in the settings panel while the request was in flight. We now
 * snapshot what each field looked like before the fetch and only apply
 * the remote value if the user hasn't touched it since.
 */
async function loadFromBackend() {
  isSyncing.value = true
  lastSyncError.value = ''
  const snapshot = {
    baseUrl:      baseUrl.value,
    modelId:      modelId.value,
    fastModelId:  fastModelId.value,
    apiKey:       apiKey.value,
    personality:  personality.value,
    birthday:     birthday.value,
    customPrompt: customPrompt.value,
  }
  const untouched = (key, current) => current === snapshot[key]
  try {
    const remote = await fetchSettings()
    if (remote.baseUrl      && untouched('baseUrl',      baseUrl.value))      baseUrl.value      = remote.baseUrl
    if (remote.modelId      && untouched('modelId',      modelId.value))      modelId.value      = remote.modelId
    if (remote.fastModelId  && untouched('fastModelId',  fastModelId.value))  fastModelId.value  = remote.fastModelId
    if (remote.apiKey       && untouched('apiKey',       apiKey.value))       apiKey.value       = remote.apiKey
    if (remote.personality  && untouched('personality',  personality.value))  personality.value  = remote.personality
    if (remote.birthday     && untouched('birthday',     birthday.value))     birthday.value     = remote.birthday
    if (remote.customPrompt && untouched('customPrompt', customPrompt.value)) customPrompt.value = remote.customPrompt
    if (remote.feishu) Object.assign(feishu, remote.feishu)
    persistLocal()
  } catch (err) {
    // Offline / backend down is fine — we still have the localStorage values.
    lastSyncError.value = err?.message || String(err)
    console.warn('[settings] load from backend failed (offline?):', err)
  } finally {
    isSyncing.value = false
  }
}

/**
 * Persist current state to both backend and localStorage. Returns true on
 * full success, false if backend save failed (local is always saved).
 */
async function save() {
  persistLocal()
  isSyncing.value = true
  lastSyncError.value = ''
  try {
    await saveSettings({
      baseUrl: baseUrl.value,
      modelId: modelId.value,
      fastModelId: fastModelId.value,
      apiKey: apiKey.value,
      personality: personality.value,
      birthday: birthday.value,
      customPrompt: customPrompt.value,
      feishu: { ...feishu },
    })
    return true
  } catch (err) {
    lastSyncError.value = err?.message || String(err)
    console.warn('[settings] save to backend failed:', err)
    return false
  } finally {
    isSyncing.value = false
  }
}

export function useSettings() {
  return {
    // State
    baseUrl, apiKey, modelId, fastModelId, personality, birthday, customPrompt, feishu,
    isSyncing, lastSyncError,
    // Derived
    chatOptions,
    // Actions
    save,
    loadFromBackend,
    persistLocal,
  }
}
