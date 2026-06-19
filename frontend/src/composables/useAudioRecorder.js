/**
 * Audio recorder composable — wraps MediaRecorder around getUserMedia and
 * uploads the resulting blob to the backend for ASR + AI reply + TTS.
 *
 * Recording lifecycle:
 *   1. start() prompts mic permission, starts MediaRecorder
 *   2. stop()  flushes the recorder; ondataavailable + onstop fire
 *   3. onstop calls api.audio.uploadAudio and surfaces results to caller
 */

import { ref } from 'vue'
import { uploadAudio } from '../api/audio.js'
import { useChat } from '../stores/useChat.js'

// Anything smaller than this is almost certainly a press-then-release-too-fast
// noise blob — we skip the upload so the backend doesn't reply "无法识别".
const MIN_BLOB_BYTES = 1200

export function useAudioRecorder() {
  const isRecording = ref(false)
  const lastError = ref('')
  let recorder = null
  let chunks = []

  const chat = useChat()

  async function start() {
    if (isRecording.value) return
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      recorder = new MediaRecorder(stream)
      chunks = []
      recorder.ondataavailable = (event) => {
        if (event.data?.size > 0) chunks.push(event.data)
      }
      recorder.onstop = async () => {
        const blob = new Blob(chunks, { type: 'audio/webm' })
        try {
          await handleUpload(blob)
        } finally {
          stream.getTracks().forEach((t) => t.stop())
        }
      }
      recorder.start()
      isRecording.value = true
    } catch (err) {
      lastError.value = err?.message || String(err)
      console.error('开始录音失败:', err)
      // Bug #5: previously the error only went to console; user saw the
      // record button do nothing forever. Surface it inside the chat panel.
      chat.pushAssistant(
        '无法访问麦克风：' + (err?.message || '权限被拒绝，请检查系统/浏览器设置。'),
      )
      await chat.scrollToBottom()
    }
  }

  function stop() {
    if (!isRecording.value || !recorder) return
    if (recorder.state !== 'inactive') recorder.stop()
    isRecording.value = false
  }

  async function handleUpload(blob) {
    // Bug #17: filter zero/tiny blobs before uploading — they always come
    // back with an ASR failure and pollute the conversation.
    if (!blob || blob.size < MIN_BLOB_BYTES) {
      chat.pushAssistant('录音时间太短，请按住按钮多说几秒~')
      await chat.scrollToBottom()
      return
    }

    chat.loading.value = true
    chat.messages.value.push({ role: 'ai', content: '识别语音中...', isThinking: true })
    await chat.scrollToBottom()
    try {
      // Bug #18: 'feishu' was hard-coded — desktop chat sessions were being
      // logged as if they came from Feishu. Tag it correctly.
      const data = await uploadAudio(blob, 'desktop')

      // Bug #3 + #15: previously appendUser ran AFTER the thinking
      // placeholder was inserted, so the AI's reply replaced the
      // placeholder and ended up BEFORE the transcribed user text in the
      // list. Drop the placeholder first, then push user → assistant in
      // natural order. This also covers the case where response is
      // present but transcription is not (user message would have been
      // skipped entirely under the old flow).
      chat.resolveThinking(null)

      if (data?.transcription) {
        chat.appendUser(data.transcription)
      }
      if (data?.response) {
        chat.pushAssistant(data.response)
      } else {
        chat.pushAssistant(
          '语音识别失败: ' + (data?.error || '无法识别语音内容'),
        )
      }
      if (data?.ttsAudio) {
        chat.pushAssistant('', { ttsAudioPath: data.ttsAudio })
      }
    } catch (err) {
      console.error('上传音频失败:', err)
      chat.resolveThinking({ role: 'ai', content: '语音处理失败，请检查网络或稍后重试。' })
    } finally {
      chat.loading.value = false
      await chat.scrollToBottom()
    }
  }

  return { isRecording, lastError, start, stop }
}
