/**
 * Settings API — round-trip persona + provider config to the backend's
 * GET/POST /settings endpoints (added in stage 1). All field names use
 * camelCase to match the backend's pydantic alias_generator.
 */

import { getJson, postJson } from './request.js'

/**
 * @typedef {Object} FeishuVoiceSettings
 * @property {boolean} [asrEnabled]
 * @property {boolean} [ttsEnabled]
 * @property {string}  [ttsVoice]
 */

/**
 * @typedef {Object} Settings
 * @property {string} baseUrl       - LLM provider api_base
 * @property {string} modelId       - Default model id (main chat + research L1)
 * @property {string} [fastModelId] - Fast model for research page summarization (L2)
 * @property {string} apiKey        - Provider api_key
 * @property {string} personality   - 'gentle' | 'active' | 'tsundere'
 * @property {string} customPrompt
 * @property {string} birthday      - ISO date YYYY-MM-DD or ''
 * @property {FeishuVoiceSettings} feishu
 */

/** @returns {Promise<Settings>} */
export async function fetchSettings() {
  return getJson('/settings')
}

/**
 * Persist a settings patch. Only fields you include are written; backend
 * ignores unknown keys.
 * @param {Partial<Settings>} patch
 * @returns {Promise<{success: true}>}
 */
export async function saveSettings(patch) {
  return postJson('/settings', patch)
}
