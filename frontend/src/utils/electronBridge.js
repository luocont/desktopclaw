/**
 * Helpers for safely accessing the Electron preload bridge
 * (`window.electronAPI`). All callers should go through these wrappers so
 * that browser/dev mode (no Electron) degrades gracefully instead of
 * throwing on `undefined.someMethod()`.
 */

/** @returns {object | null} */
export function getElectronApi() {
  if (typeof window === 'undefined') return null
  return window.electronAPI || null
}

/**
 * Check whether `window.electronAPI[fnName]` is callable.
 * @param {string} fnName
 * @returns {boolean}
 */
export function hasElectronApi(fnName) {
  const api = getElectronApi()
  return !!(api && typeof api[fnName] === 'function')
}

/**
 * Invoke a method on the bridge if it exists; return undefined otherwise.
 * Useful for fire-and-forget operations like `setIgnoreMouseEvents`.
 * @param {string} fnName
 * @param  {...any} args
 */
export function callElectronApi(fnName, ...args) {
  if (hasElectronApi(fnName)) {
    return getElectronApi()[fnName](...args)
  }
  return undefined
}
