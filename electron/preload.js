const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  /**
   * 提交输入框数据到后端
   * @param {string} inputValue - 输入框内容
   * @returns {Promise<Object>} 后端返回的结果
   */
  submitInput: (inputValue) => ipcRenderer.invoke('submit-input', inputValue),

  /**
   * 从后端获取数据
   * @returns {Promise<Object>} 后端返回的数据
   */
  getBackendData: () => ipcRenderer.invoke('get-backend-data')
})
