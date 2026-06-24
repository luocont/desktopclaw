import request from './request.js'

/**
 * @returns {Promise<{
 *   success: boolean,
 *   userMemory: { markdown: string, historyPreview: string },
 *   strategies: object[],
 *   stats: { strategyCount: number, pendingCount: number, readyCount: number, failedCount: number },
 *   embeddingModel: { status: string, progress: number|null, model: string, message: string, error: string, resumed: boolean }
 * }>}
 */
export async function fetchMemory() {
  const { data } = await request.get('/memory')
  return data
}

/** Retry or resume embedding model download via backend preload. */
export async function retryEmbeddingDownload() {
  const { data } = await request.post('/memory/retry-embedding')
  return data
}
