const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // 发送 HTTP POST 请求到后端
  sendMessage: (message) => ipcRenderer.invoke('send-message', message),
  
  // SSE 连接相关
  connectFeishuSSE: () => ipcRenderer.invoke('connect-feishu-sse'),
  disconnectFeishuSSE: () => ipcRenderer.invoke('disconnect-feishu-sse'),
  onFeishuEvent: (callback) => {
    ipcRenderer.on('feishu-event', (event, data) => callback(data))
  },
  removeFeishuListener: () => {
    ipcRenderer.removeAllListeners('feishu-event')
  }
})
