/**
 * Resize composable — drives `petScale` when the user grabs the resize
 * handle. The actual PIXI re-layout is delegated to a callback the caller
 * (Live2DStage) provides so we don't tightly couple the resize gesture to
 * the model store.
 */

import { ref } from 'vue'
import { MIN_SCALE, MAX_SCALE } from '../utils/constants.js'

/**
 * @param {object} options
 * @param {import('vue').Ref<number>} options.scale  - reactive scale ref to mutate
 * @param {() => void} [options.onResize]            - called after each scale update
 */
export function useResize({ scale, onResize }) {
  const isResizing = ref(false)
  const startX = ref(0)
  const startY = ref(0)
  const startScale = ref(1)

  function start(event) {
    isResizing.value = true
    startX.value = event.clientX
    startY.value = event.clientY
    startScale.value = scale.value
    event.preventDefault?.()
  }

  function move(event) {
    if (!isResizing.value) return
    const dx = event.clientX - startX.value
    const dy = event.clientY - startY.value
    const delta = (dx + dy) / 2
    const next = Math.min(MAX_SCALE, Math.max(MIN_SCALE, startScale.value + delta / 200))
    scale.value = next
    onResize?.()
  }

  function end() {
    if (isResizing.value) isResizing.value = false
  }

  return { isResizing, start, move, end }
}
