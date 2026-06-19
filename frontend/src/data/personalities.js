/**
 * Personality option metadata used by the SettingsPanel.
 *
 * Note: the backend's litellm provider only recognises the literal values
 * `gentle` / `active` / `tsundere` — extending this list requires also
 * extending `LiteLLMProvider.chat` in the backend.
 */

export const personalityOptions = [
  { value: 'gentle', label: '温柔', description: '说话温柔体贴' },
  { value: 'active', label: '活泼', description: '活泼开朗' },
  { value: 'tsundere', label: '傲娇', description: '口是心非' },
]

export const DEFAULT_PERSONALITY = 'gentle'
