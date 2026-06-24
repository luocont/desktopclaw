const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  sendMessage: (message, options) => ipcRenderer.invoke('send-message', message, options),

  connectFeishuSSE: () => ipcRenderer.invoke('connect-feishu-sse'),
  disconnectFeishuSSE: () => ipcRenderer.invoke('disconnect-feishu-sse'),
  onFeishuEvent: (callback) => {
    ipcRenderer.on('feishu-event', (event, data) => callback(data))
  },
  removeFeishuListener: () => {
    ipcRenderer.removeAllListeners('feishu-event')
  },
  setIgnoreMouseEvents: (ignore, options) => ipcRenderer.invoke('set-ignore-mouse-events', ignore, options),
  scanLive2DModels: () => ipcRenderer.invoke('scan-live2d-models'),
  resizePetWindow: (x, y, width, height) => ipcRenderer.invoke('resize-pet-window', x, y, width, height),
  movePetWindow: (x, y) => ipcRenderer.invoke('move-pet-window', x, y),
  getWindowPosition: () => ipcRenderer.invoke('get-window-position'),
  closeWindow: () => ipcRenderer.invoke('close-window'),
  closeChatWindow: () => ipcRenderer.invoke('close-chat-window'),

  launchUi: (mode, remember) => ipcRenderer.invoke('launch-ui', { mode, remember }),
  getUiPreference: () => ipcRenderer.invoke('get-ui-preference'),
  switchUiMode: (mode) => ipcRenderer.invoke('switch-ui-mode', mode),

  syncChatState: (payload) => ipcRenderer.invoke('sync-chat-state', payload),
  getChatState: () => ipcRenderer.invoke('get-chat-state'),
  onChatStateUpdated: (callback) => {
    ipcRenderer.on('chat-state-updated', (_event, data) => callback(data))
  },
  removeChatStateListener: () => {
    ipcRenderer.removeAllListeners('chat-state-updated')
  },

  getScreenInfo: () => ipcRenderer.invoke('get-screen-info'),
  onScreenInfoUpdated: (callback) => {
    ipcRenderer.on('screen-info-updated', (event, data) => callback(data))
  },
  removeScreenInfoListener: () => {
    ipcRenderer.removeAllListeners('screen-info-updated')
  },
})
