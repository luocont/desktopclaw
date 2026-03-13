const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // 发送 HTTP POST 请求到后端
  sendMessage: (message) => ipcRenderer.invoke('send-message', message)
})
