/**
 * Dialog drag composable — drag the chat bubble header to move the entire
 * pet window (since the bubble lives inside the same Electron window).
 * Mirrors useDrag but anchored to a different DOM event source.
 */

import { ref } from 'vue'
import { hasElectronApi, callElectronApi } from '../utils/electronBridge.js'

export function useDialogDrag() {
  const isDragging = ref(false)
  const startMouseX = ref(0)
  const startMouseY = ref(0)
  const startWindowX = ref(0)
  const startWindowY = ref(0)

  function start(event) {
    if (event?.target?.closest?.('.bubble-header-btns')) return
    isDragging.value = true
    startMouseX.value = event.screenX
    startMouseY.value = event.screenY
    if (hasElectronApi('getWindowPosition')) {
      callElectronApi('getWindowPosition').then((pos) => {
        startWindowX.value = pos?.x || 0
        startWindowY.value = pos?.y || 0
      })
    }
    document.addEventListener('mousemove', onMove)
    document.addEventListener('mouseup', stop)
  }

  function onMove(event) {
    if (!isDragging.value) return
    const dx = event.screenX - startMouseX.value
    const dy = event.screenY - startMouseY.value
    callElectronApi('movePetWindow', startWindowX.value + dx, startWindowY.value + dy)
  }

  function stop() {
    isDragging.value = false
    document.removeEventListener('mousemove', onMove)
    document.removeEventListener('mouseup', stop)
  }

  return { isDragging, start, stop }
}
