# Backend 后端文件夹

在此文件夹中编写你的后端代码。

## 已预留的 IPC 路由

### 1. `submit-input` - 提交输入框数据
- **前端调用**: `window.electronAPI.submitInput(inputValue)`
- **文件位置**: `electron/main.js`
- **用途**: 接收前端输入框的内容

### 2. `get-backend-data` - 获取后端数据
- **前端调用**: `window.electronAPI.getBackendData()`
- **文件位置**: `electron/main.js`
- **用途**: 从后端获取数据

## 如何集成后端

在 `electron/main.js` 中引入你的后端服务:

```javascript
const BackendService = require('../backend')
const backend = new BackendService()

ipcMain.handle('submit-input', async (event, inputValue) => {
  const result = await backend.processInput(inputValue)
  return result
})
```
