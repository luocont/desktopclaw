/**
 * Unified HTTP request layer for the DesktopClaw frontend.
 *
 * Design:
 *  - Single axios instance with a dynamic baseURL (re-evaluated per call so
 *    settings updates take effect immediately without rebuilding the client).
 *  - Request interceptor injects `Authorization: Bearer <apiKey>` when the
 *    settings store has supplied one via `registerAuthProvider`.
 *  - Response interceptor normalizes errors into `ApiError` with a
 *    user-friendly Chinese message, classifying network / timeout / HTTP
 *    failures consistently. Business errors (`{success: false, error}`) are
 *    surfaced by callers since the SSE-capable `/chat` path needs the raw
 *    body.
 */

import axios from 'axios'
import { getBaseUrl } from './config.js'

/** @type {(() => string | null) | null} */
let _authProvider = null

/**
 * Register a function that returns the current API key (or null/empty).
 * Called by the settings store at app boot so the request interceptor can
 * read the latest value on every request without holding a reactive ref.
 * @param {() => string | null} fn
 */
export function registerAuthProvider(fn) {
  _authProvider = fn
}

/**
 * Custom error type — request callers can `instanceof ApiError` to branch on
 * known failure modes vs. unexpected exceptions.
 */
export class ApiError extends Error {
  constructor(message, { kind = 'unknown', status = 0, original = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.kind = kind // 'network' | 'timeout' | 'http' | 'business' | 'unknown'
    this.status = status
    this.original = original
  }
}

/**
 * @returns {import('axios').AxiosInstance}
 */
function createInstance() {
  const instance = axios.create({
    timeout: 600000, // 10 min — chat / audio uploads can be slow with tools
    headers: { 'Content-Type': 'application/json' },
  })

  instance.interceptors.request.use((config) => {
    // Resolve baseURL lazily so localStorage edits take effect right away.
    if (!config.baseURL) config.baseURL = getBaseUrl()
    if (_authProvider) {
      const key = _authProvider()
      if (key && !config.headers?.Authorization) {
        config.headers = config.headers || {}
        config.headers.Authorization = `Bearer ${key}`
      }
    }
    return config
  })

  instance.interceptors.response.use(
    (response) => response,
    (error) => Promise.reject(normalizeError(error)),
  )

  return instance
}

function normalizeError(error) {
  if (error instanceof ApiError) return error
  if (error?.code === 'ECONNABORTED' || /timeout/i.test(error?.message || '')) {
    return new ApiError('请求超时，请稍后重试', { kind: 'timeout', original: error })
  }
  if (error?.response) {
    const { status, data } = error.response
    const serverMsg = (data && (data.error || data.message)) || ''
    return new ApiError(
      serverMsg || `服务器返回错误 (HTTP ${status})`,
      { kind: 'http', status, original: error },
    )
  }
  if (error?.request) {
    return new ApiError('网络连接失败，请确认后端服务已启动', { kind: 'network', original: error })
  }
  return new ApiError(error?.message || '未知错误', { kind: 'unknown', original: error })
}

const request = createInstance()

/**
 * Convenience POST that returns response.data and unwraps `{success, ...}`
 * envelopes used by the backend. Throws ApiError on transport failures and
 * a 'business' ApiError when `success === false`.
 */
export async function postJson(path, body, config = {}) {
  const { data } = await request.post(path, body, config)
  if (data && typeof data === 'object' && data.success === false) {
    throw new ApiError(data.error || '业务错误', { kind: 'business', original: data })
  }
  return data
}

export async function getJson(path, config = {}) {
  const { data } = await request.get(path, config)
  return data
}

export default request
