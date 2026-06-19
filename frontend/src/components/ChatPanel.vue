<template>
  <transition name="bubble-fade">
    <div
      v-show="visible"
      class="dialog-bubble glass-card"
      :class="{ expanded, dragging: dialogDrag.isDragging.value }"
      ref="bubbleEl"
    >
      <div class="bubble-header" @mousedown="dialogDrag.start">
        <span class="bubble-title">DesktopClaw</span>
        <div class="bubble-header-btns">
          <button
            class="bubble-expand-btn"
            @click.stop="$emit('toggleExpand')"
            :title="expanded ? '缩小' : '放大'"
            :aria-label="expanded ? '缩小对话框' : '放大对话框'"
          >
            <Maximize2 :size="14" v-if="!expanded" />
            <Minimize2 :size="14" v-else />
          </button>
          <button class="bubble-close" @click.stop="$emit('close')" aria-label="关闭对话框">
            <X :size="14" />
          </button>
        </div>
      </div>

      <div class="bubble-messages" ref="messagesEl">
        <MessageBubble
          v-for="(msg, index) in chat.messages.value"
          :key="index"
          :message="msg"
        />
      </div>

      <div class="bubble-input">
        <input
          v-model="chat.inputValue.value"
          @keydown.enter="onEnterKey"
          @compositionstart="composing = true"
          @compositionend="composing = false"
          placeholder="和我说点什么..."
          :disabled="chat.loading.value || recorder.isRecording.value"
          class="bubble-input-field"
        />
        <!-- Bug #19: while a request is in flight the send button now
             becomes a Cancel button that aborts the stream. Previously
             chat.abort() existed but the UI never invoked it. -->
        <button
          v-if="!chat.loading.value"
          @click="onSend"
          :disabled="!chat.inputValue.value.trim() || recorder.isRecording.value"
          class="bubble-send-btn"
          aria-label="发送消息"
        >
          <Send :size="16" />
        </button>
        <button
          v-else
          @click="onCancel"
          class="bubble-send-btn cancel"
          aria-label="取消请求"
          title="取消"
        >
          <X :size="16" />
        </button>
        <button
          @mousedown="recorder.start"
          @mouseup="recorder.stop"
          @mouseleave="recorder.stop"
          @touchstart.prevent="recorder.start"
          @touchend.prevent="recorder.stop"
          :disabled="chat.loading.value"
          :class="['bubble-record-btn', { recording: recorder.isRecording.value }]"
          :aria-label="recorder.isRecording.value ? '停止录音' : '开始录音'"
        >
          <Mic :size="16" />
        </button>
      </div>
      <div class="bubble-arrow"></div>
    </div>
  </transition>
</template>

<script setup>
import { ref, watch } from 'vue'
import { Maximize2, Minimize2, X, Send, Mic } from 'lucide-vue-next'
import MessageBubble from './MessageBubble.vue'
import { useChat } from '../stores/useChat.js'
import { useDialogDrag } from '../composables/useDialogDrag.js'
import { useAudioRecorder } from '../composables/useAudioRecorder.js'

const props = defineProps({
  visible: { type: Boolean, default: false },
  expanded: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'toggleExpand', 'sized'])

const chat = useChat()
const recorder = useAudioRecorder()
const dialogDrag = useDialogDrag()

const bubbleEl = ref(null)
const messagesEl = ref(null)
// Bug #2: track IME composition so pressing Enter to confirm a CJK
// candidate doesn't accidentally send a half-typed pinyin message.
const composing = ref(false)

// Wire the messagesRef in the store so scrollToBottom can find the element.
chat.messagesRef.value = null
watch(messagesEl, (el) => { chat.messagesRef.value = el }, { immediate: true })

// Notify parent whenever the bubble's bounding box changes so it can
// resize the Electron window to encompass the dialog.
watch([() => props.visible, () => props.expanded], () => {
  // Defer to next paint so the DOM has settled before measuring.
  requestAnimationFrame(() => emit('sized', bubbleEl.value))
})

defineExpose({ bubbleEl })

function onEnterKey(e) {
  // Belt-and-braces: skip if composition is active in either the DOM event
  // or the local flag (some IMEs miss compositionend right before keydown).
  if (composing.value || e.isComposing || e.keyCode === 229) return
  onSend()
}

async function onSend() {
  await chat.send()
}

function onCancel() {
  chat.abort()
}
</script>

<style scoped>
.bubble-send-btn.cancel {
  background: var(--error, #c0392b);
}
.bubble-send-btn.cancel:hover {
  filter: brightness(1.1);
}
</style>
