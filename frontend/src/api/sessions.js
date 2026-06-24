import request from './request.js'

/**
 * @returns {Promise<{ success: boolean, sessions: Array<{ key, created_at, updated_at, message_count }> }>}
 */
export async function fetchSessions() {
  const { data } = await request.get('/sessions')
  return data
}

/**
 * @param {string} sessionKey
 * @returns {Promise<{ success: boolean, key: string, messages: object[], updated_at: string }>}
 */
export async function fetchSessionMessages(sessionKey) {
  const encoded = encodeURIComponent(sessionKey)
  const { data } = await request.get(`/sessions/${encoded}/messages`)
  return data
}

/**
 * @param {string} sessionKey
 * @returns {Promise<{ success: boolean, error?: string }>}
 */
export async function deleteSession(sessionKey) {
  const encoded = encodeURIComponent(sessionKey)
  const { data } = await request.delete(`/sessions/${encoded}`)
  return data
}
