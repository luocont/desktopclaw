/**
 * Window drag composable — moves the Electron pet window when the user
 * grabs the Live2D area. The window's screen position drives positioning
 * (we don't translate the DOM), so multi-monitor edges are handled by the
 * OS window manager naturally.
 *
 * Returns handlers the caller wires to mousedown / global mousemove /
 * global mouseup.
 */

import { ref } from 'vue'
import { hasElectronApi, callElectronApi } from '../utils/electronBridge.js'

/**
 * @param {{ onClickThroughChange?: (ignore: boolean) => void }} [opts]
 */
export function useDrag(opts = {}) {
  const isDragging = ref(false)
  const dragMoved = ref(false)
  const startScreenX = ref(0)
  const startScreenY = ref(0)
  const startWindowX = ref(0)
  const startWindowY = ref(0)

  async function start(event) {
    isDragging.value = true
    dragMoved.value = false
    startScreenX.value = event.screenX
    startScreenY.value = event.screenY
    if (hasElectronApi('getWindowPosition')) {
      const pos = await callElectronApi('getWindowPosition')
      startWindowX.value = pos?.x || 0
      startWindowY.value = pos?.y || 0
    }
    opts.onClickThroughChange?.(false)
    event.preventDefault?.()
  }

  function move(event) {
    if (!isDragging.value) return
    if (event.buttons !== 1) {
      isDragging.value = false
      return
    }
    const dx = event.screenX - startScreenX.value
    const dy = event.screenY - startScreenY.value
    // Bug #13: dragMoved used to be set but never read. Apply a small
    // dead-zone so accidental jitter on a click is not treated as a drag,
    // and expose the flag (consumers can read it after `end()` to decide
    // whether a follow-up click should be suppressed).
    if (!dragMoved.value && Math.abs(dx) + Math.abs(dy) < 3) return
    dragMoved.value = true
    callElectronApi('movePetWindow', startWindowX.value + dx, startWindowY.value + dy)
  }

  function end() {
    if (isDragging.value) {
      isDragging.value = false
      // Click-through is owned by App.vue mouseenter/leave — re-enabling
      // here left the window ignoring clicks right after a drag.
    }
  }

  return { isDragging, dragMoved, start, move, end }
}
