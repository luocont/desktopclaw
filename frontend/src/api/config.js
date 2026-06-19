/**
 * API endpoint configuration — single source of truth for the backend base URL.
 *
 * NOTE: The CSP whitelist in `vite.config.mjs` and `index.html` (and the
 * Electron main-process CSP in `electron/main.js`) must continue to allow
 * `connect-src http://127.0.0.1:3000`. If you change DEFAULT_API_URL to a
 * non-localhost address, update those three places too.
 */

export const DEFAULT_API_URL = 'http://127.0.0.1:3000'

/** DesktopClaw HTTP API (settings/chat). NOT the LLM provider base URL. */
const BACKEND_STORAGE_KEY = 'pet_backend_api_url'
const LEGACY_LLM_BASE_KEY = 'pet_base_url'

/**
 * One-time migration: older builds stored the LLM api_base in `pet_base_url`
 * and also used that key for DesktopClaw backend requests — sending /settings
 * to the LLM host. Only migrate when the legacy value is clearly our API port.
 */
function migrateStorageKeys() {
  try {
    const backend = localStorage.getItem(BACKEND_STORAGE_KEY)
    const legacy = localStorage.getItem(LEGACY_LLM_BASE_KEY)
    if (!backend && legacy) {
      const normalized = legacy.trim().replace(/\/+$/, '')
      if (/^https?:\/\/(127\.0\.0\.1|localhost):3000$/i.test(normalized)) {
        localStorage.setItem(BACKEND_STORAGE_KEY, normalized)
      }
    }
  } catch {
    /* ignore */
  }
}

migrateStorageKeys()

/**
 * Resolve the DesktopClaw backend base URL.
 * Priority: localStorage override (`pet_backend_api_url`) → DEFAULT_API_URL.
 *
 * LLM provider `api_base` is stored separately as `pet_base_url` in the
 * settings store — never read that key here.
 * @returns {string}
 */
export function getBaseUrl() {
  try {
    const stored = localStorage.getItem(BACKEND_STORAGE_KEY)
    if (stored && stored.trim()) return stored.trim().replace(/\/+$/, '')
  } catch {
    // localStorage may be unavailable in some contexts; fall through.
  }
  return DEFAULT_API_URL
}

/**
 * Persist a DesktopClaw backend URL override (or clear when empty).
 * @param {string} value
 */
export function setBackendUrl(value) {
  try {
    if (value && value.trim()) {
      localStorage.setItem(BACKEND_STORAGE_KEY, value.trim().replace(/\/+$/, ''))
    } else {
      localStorage.removeItem(BACKEND_STORAGE_KEY)
    }
  } catch {
    // ignore
  }
}
