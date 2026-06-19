/**
 * Pet window size & scale constants — single source of truth so multiple
 * composables / components agree on dimensions.
 */

export const BASE_WIDTH = 300
export const BASE_HEIGHT = 400
export const MIN_SCALE = 0.5
export const MAX_SCALE = 2.0

/** localStorage keys grouped here so audits are easy. */
export const STORAGE_KEYS = {
  baseUrl: 'pet_base_url',
  apiKey: 'pet_api_key',
  modelId: 'pet_model_id',
  fastModelId: 'pet_fast_model_id',
  personality: 'pet_personality',
  birthday: 'pet_birthday',
  customPrompt: 'pet_custom_prompt',
}
