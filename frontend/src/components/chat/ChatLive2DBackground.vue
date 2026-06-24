<template>
  <div ref="containerEl" class="chat-live2d-bg" aria-hidden="true">
    <canvas ref="canvasEl" class="chat-live2d-canvas" />
    <div v-if="!live2d.isModelLoaded.value && live2d.modelError.value" class="chat-live2d-hint">
      {{ live2d.modelError.value }}
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useLive2D } from '../../stores/useLive2D.js'
import { BASE_HEIGHT } from '../../utils/constants.js'

const live2d = useLive2D()
const containerEl = ref(null)
const canvasEl = ref(null)
let resizeObserver = null

function syncScale() {
  const el = containerEl.value
  if (!el) return
  const h = el.clientHeight
  if (h <= 0) return
  const targetScale = Math.min(Math.max(h / BASE_HEIGHT, 0.45), 0.75)
  live2d.petScale.value = targetScale
  live2d.applyResize()
}

onMounted(async () => {
  setTimeout(async () => {
    syncScale()
    await live2d.loadModel(canvasEl.value, { interactive: false })
  }, 500)

  if (typeof ResizeObserver !== 'undefined' && containerEl.value) {
    resizeObserver = new ResizeObserver(() => syncScale())
    resizeObserver.observe(containerEl.value)
  }
})

onUnmounted(() => {
  resizeObserver?.disconnect()
  resizeObserver = null
  live2d.cleanup()
})
</script>

<style scoped>
.chat-live2d-bg {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 280px;
  height: 350px;
  padding-bottom: 100px;
  pointer-events: none;
  z-index: 1;
  overflow: hidden;
  display: flex;
  align-items: flex-end;
  justify-content: flex-end;
}

.chat-live2d-canvas {
  display: block;
  max-width: 100%;
  max-height: 100%;
}

.chat-live2d-hint {
  position: absolute;
  bottom: 24px;
  font-size: 12px;
  color: var(--chat-text-muted);
  z-index: 1;
}
</style>
