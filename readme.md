无论比尔大飞机check
# DesktopClaw

Vue3 + Electron 桌面应用

## 项目结构

```
desktopclaw/
├── electron/           # Electron 主进程代码
│   ├── main.js        # 主进程入口 (包含 IPC 路由)
│   └── preload.js     # 预加载脚本 (暴露 API 给渲染进程)
├── src/               # Vue3 前端代码
│   ├── index.html
│   ├── main.js
│   ├── App.vue        # 主组件 (含输入框)
│   └── style.css
├── backend/           # 后端代码 (预留)
│   ├── index.js       # 后端服务入口
│   └── README.md
├── package.json
└── vite.config.js
```

## 安装依赖

```bash
npm install
```

## 开发模式

```bash
npm run dev
```

这会同时启动:
- Vite 开发服务器 (http://localhost:5173)
- Electron 窗口

## 输入框路由说明

### 前端 → 后端 IPC 路由

**路由名称**: `submit-input`

**前端调用方式** ([src/App.vue](src/App.vue)):
```javascript
const result = await window.electronAPI.submitInput(inputValue)
```

**后端接收位置** ([electron/main.js](electron/main.js)):
```javascript
ipcMain.handle('submit-input', async (event, inputValue) => {
  // 在这里处理输入数据
  console.log('收到前端输入:', inputValue)
  return { success: true, data: inputValue }
})
```

### 另一个可用路由

**路由名称**: `get-backend-data`

**前端调用**:
```javascript
const data = await window.electronAPI.getBackendData()
```

## 如何编写后端代码

1. 在 [backend/index.js](backend/index.js) 中编写你的后端逻辑
2. 在 [electron/main.js](electron/main.js) 中引入并调用
3. 参考 [backend/README.md](backend/README.md) 了解更多

## 构建生产版本

```bash
npm run build
```

这会先构建 Vue3 应用,然后使用 electron-builder 打包成桌面应用。
