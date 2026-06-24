<template>
  <div class="chat-composer-wrap">
    <div class="chat-composer">
      <textarea
        ref="textareaEl"
        v-model="chat.inputValue.value"
        class="chat-composer-input"
        placeholder="发消息..."
        rows="1"
        :disabled="chat.loading.value || recorder.isRecording.value"
        @keydown="onKeydown"
        @compositionstart="composing = true"
        @compositionend="composing = false"
        @input="autoResize"
      />
      <div class="chat-composer-toolbar">
        <div class="chat-composer-actions">
          <button
            v-for="chip in chips"
            :key="chip"
            type="button"
            class="chat-action-chip"
            @click="insertChip(chip)"
          >
            {{ chip }}
          </button>
        </div>
        <div class="chat-composer-right">
          <button
            type="button"
            :class="['chat-mic-btn', { recording: recorder.isRecording.value }]"
            :disabled="chat.loading.value"
            aria-label="语音输入"
            @mousedown="recorder.start"
            @mouseup="recorder.stop"
            @mouseleave="recorder.stop"
            @touchstart.prevent="recorder.start"
            @touchend.prevent="recorder.stop"
          >
            <Mic :size="16" />
          </button>
          <button
            v-if="!chat.loading.value"
            type="button"
            class="chat-send-btn"
            :disabled="!chat.inputValue.value.trim() || recorder.isRecording.value"
            aria-label="发送"
            @click="onSend"
          >
            <Send :size="16" />
          </button>
          <button
            v-else
            type="button"
            class="chat-send-btn cancel"
            aria-label="取消"
            @click="chat.abort()"
          >
            <X :size="16" />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { Send, Mic, X } from 'lucide-vue-next'
import { useChat } from '../../stores/useChat.js'
import { useAudioRecorder } from '../../composables/useAudioRecorder.js'

const emit = defineEmits(['sent'])

const chat = useChat()
const recorder = useAudioRecorder()
const composing = ref(false)
const textareaEl = ref(null)

const chips = ['快速', '编程', '研究', '写作', '翻译']

function autoResize() {
  const el = textareaEl.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = `${Math.min(el.scrollHeight, 160)}px`
}

function insertChip(label) {
  const prefix = chat.inputValue.value.trim()
  chat.inputValue.value = prefix ? `${prefix} ${label}：` : `${label}：`
  autoResize()
  textareaEl.value?.focus()
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    if (composing.value || e.isComposing || e.keyCode === 229) return
    e.preventDefault()
    onSend()
  }
}

async function onSend() {
  await chat.send()
  emit('sent')
  autoResize()
}

onMounted(() => autoResize())
</script>
