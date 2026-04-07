const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  sendMessage: (message) => ipcRenderer.invoke('send-message', message),

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
  resizePetWindow: (x, y, width, height) => ipcRenderer.invoke('resize-pet-window', x, y, width, height)
})
