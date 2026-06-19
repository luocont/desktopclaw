/**
 * Audio API — uploads recorded webm/opus blobs to POST /audio/upload, where
 * the backend transcribes via DashScope ASR and (optionally) returns a
 * synthesized TTS audio URL alongside the agent's text response.
 */

import request from './request.js'

/**
 * @typedef {Object} AudioUploadResult
 * @property {boolean} success
 * @property {string} [transcription]
 * @property {string} [response]
 * @property {string} [ttsAudio]      - URL to a generated MP3 served by /media
 * @property {string} [error]
 */

/**
 * @param {Blob} audioBlob
 * @param {string} [channel='desktop']  - was 'feishu' but desktop voice
 *   uploads should not impersonate the Feishu channel (Bug #18). Pass
 *   'feishu' explicitly when the audio actually came from there.
 * @returns {Promise<AudioUploadResult>}
 */
export async function uploadAudio(audioBlob, channel = 'desktop') {
  const formData = new FormData()
  formData.append('audio', audioBlob, 'recording.webm')
  formData.append('channel', channel)

  // Override the JSON Content-Type from the default headers so axios sets the
  // correct multipart boundary. Timeout overrides the default in case the
  // ASR backend is slow.
  const { data } = await request.post('/audio/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 600000,
  })
  return data
}
