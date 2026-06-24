/**
 * Turn raw backend LLM / network errors into user-facing chat copy.
 * @param {string} raw
 * @returns {string}
 */
export function formatLlmError(raw) {
  const text = (raw || '').trim()
  if (!text) return '无法连接到大模型服务，请稍后重试。'

  const lower = text.toLowerCase()
  if (
    lower.includes('authentication') ||
    lower.includes('api key') ||
    lower.includes('invalid_request_error') ||
    text.includes('认证')
  ) {
    return '大模型 API 认证失败，请检查设置中的 API Key 是否正确。'
  }
  if (
    lower.includes('connection') ||
    lower.includes('timeout') ||
    lower.includes('network') ||
    lower.includes('connect') ||
    text.includes('连接') ||
    text.includes('超时')
  ) {
    return '无法连接到大模型服务，请检查网络或 API 地址是否可用。'
  }
  if (lower.includes('rate limit') || lower.includes('429')) {
    return '大模型请求过于频繁，请稍后再试。'
  }
  if (text.startsWith('Error calling LLM:')) {
    return `大模型调用失败：${text.slice('Error calling LLM:'.length).trim()}`
  }
  if (text.startsWith('Error:')) {
    return `大模型调用失败：${text.slice('Error:'.length).trim()}`
  }
  return `大模型调用失败：${text}`
}
