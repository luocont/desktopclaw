/**
 * Click-through composable — toggles `setIgnoreMouseEvents` on the Electron
 * window so the pet area is clickable but the rest of the (transparent)
 * window passes mouse events through to whatever is below it on the desktop.
 */

import { hasElectronApi, callElectronApi } from '../utils/electronBridge.js'

export function useClickThrough() {
  function set(ignore) {
    if (hasElectronApi('setIgnoreMouseEvents')) {
      callElectronApi('setIgnoreMouseEvents', ignore, { forward: true })
    }
  }
  return { set }
}
