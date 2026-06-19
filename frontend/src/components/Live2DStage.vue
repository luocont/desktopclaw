<template>
  <div
    class="live2d-wrapper"
    :style="{ width: width + 'px', height: height + 'px' }"
    @mousedown="onMouseDown"
  >
    <canvas ref="canvasEl" id="live2d-canvas"></canvas>
    <div v-if="!live2d.isModelLoaded.value" class="live2d-loading">
      {{ live2d.modelError.value || '加载中...' }}
    </div>
    <div class="resize-handle" @mousedown.stop="onResizeStart" title="拖动缩放">
      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
        <path d="M11 1L1 11M11 5L5 11M11 9L9 11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
      </svg>
    </div>
    <button class="close-btn" @mousedown.stop @click.stop="$emit('close')" title="退出桌宠" aria-label="退出桌宠">
      <X :size="14" />
    </button>

    <InteractionBubble
      :visible="reminder.showInteractionBubble.value"
      :message="reminder.interactionMessage.value"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { X } from 'lucide-vue-next'
import InteractionBubble from './InteractionBubble.vue'
import { useLive2D } from '../stores/useLive2D.js'
import { useReminder } from '../stores/useReminder.js'
import { useDrag } from '../composables/useDrag.js'
import { useResize } from '../composables/useResize.js'
import { useClickThrough } from '../composables/useClickThrough.js'

const emit = defineEmits(['close'])

const live2d = useLive2D()
const reminder = useReminder()
const click = useClickThrough()

const canvasEl = ref(null)

const drag = useDrag({
  onClickThroughChange: (ignore) => click.set(ignore),
})
const resize = useResize({
  scale: live2d.petScale,
  onResize: () => live2d.applyResize(),
})

const width = computed(() => live2d.petWidth())
const height = computed(() => live2d.petHeight())

function onMouseDown(event) {
  drag.start(event)
}
function onResizeStart(event) {
  resize.start(event)
}

function onMouseMove(event) {
  if (resize.isResizing.value) { resize.move(event); return }
  drag.move(event)
}
function onMouseUp() {
  resize.end()
  drag.end()
}

onMounted(async () => {
  // Defer to ensure cubism core has had time to load.
  setTimeout(() => live2d.loadModel(canvasEl.value), 500)
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
})

onUnmounted(() => {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  live2d.cleanup()
})
</script>
