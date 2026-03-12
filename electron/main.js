const { app, BrowserWindow, ipcMain } = require('electron')
const path = require('path')

let mainWindow

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173')
    mainWindow.webContents.openDevTools()
  } else {
    mainWindow.loadFile(path.join(__dirname, '../dist/index.html'))
  }
}

app.whenReady().then(createWindow)

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow()
  }
})

// ==========================================
// IPC 通信路由 - 输入框数据传递到后端
// ==========================================

/**
 * 路由: 'submit-input'
 * 用途: 接收前端输入框的数据
 *
 * 前端调用方式:
 * window.electronAPI.submitInput(inputValue)
 *
 * @param {string} inputValue - 输入框的内容
 */
ipcMain.handle('submit-input', async (event, inputValue) => {
  console.log('收到前端输入:', inputValue)

  // TODO: 在这里调用后端处理逻辑
  // 例如: const result = await backendService.processInput(inputValue)

  return {
    success: true,
    message: '数据已收到',
    data: inputValue
  }
})

/**
 * 路由: 'get-backend-data'
 * 用途: 从后端获取数据
 *
 * 前端调用方式:
 * window.electronAPI.getBackendData()
 */
ipcMain.handle('get-backend-data', async () => {
  // TODO: 在这里调用后端获取数据逻辑

  return {
    success: true,
    data: null
  }
})
