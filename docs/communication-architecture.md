# 前后端通信架构文档

## 项目整体结构

```
desktopclaw/
├── frontend/                    # 前端 (Vue 3 + Electron)
│   ├── electron/
│   │   ├── main.js             # Electron主进程
│   │   └── preload.js          # 预加载脚本 (IPC桥接)
│   ├── src/
│   │   ├── App.vue             # 主组件
│   │   └── main.js             # Vue入口
│   └── package.json
│
└── backend/                     # 后端
    ├── desktopclaw/            # Python后端主模块
    │   ├── api/
    │   │   └── server.py       # HTTP API服务器
    │   ├── bus/
    │   │   ├── events.py       # 消息事件定义
    │   │   └── queue.py        # 消息总线
    │   ├── channels/           # 多渠道适配器
    │   │   ├── base.py         # 基类
    │   │   ├── manager.py      # 渠道管理器
    │   │   ├── whatsapp.py     # WhatsApp渠道
    │   │   └── ...             # 其他渠道
    │   ├── agent/
    │   │   └── loop.py         # AI代理核心引擎
    │   └── cli/
    │       └── commands.py     # CLI命令入口
    │
    └── bridge/                  # Node.js WebSocket桥接
        └── src/
            ├── server.ts        # WebSocket服务器
            └── whatsapp.ts      # WhatsApp客户端
```

---

## 通信架构概览

### 架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              前端 (Frontend)                            │
│  ┌─────────────────┐    IPC     ┌─────────────────┐                    │
│  │   Vue App       │ ◄────────► │  Electron Main  │                    │
│  │  (App.vue)      │            │  (main.js)      │                    │
│  └────────┬────────┘            └────────┬────────┘                    │
│           │ HTTP (axios)                 │ HTTP (node:http)            │
│           │ (浏览器直连)                  │ (Electron IPC转发)          │
└───────────┼───────────────────────────────┼────────────────────────────┘
            │                               │
            ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           后端 (Backend)                                │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                    HTTP API Server (127.0.0.1:3000)             │   │
│  │    POST /chat  │  GET /chat/stream  │  OPTIONS (CORS)          │   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
│                                │                                        │
│                                ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                      MessageBus (异步队列)                       │   │
│  │           inbound Queue  ◄───  outbound Queue                   │   │
│  └─────────┬───────────────────────────────────┬───────────────────┘   │
│            │                                   ▲                        │
│            ▼                                   │                        │
│  ┌─────────────────────┐            ┌─────────────────────┐            │
│  │    AgentLoop        │            │  ChannelManager     │            │
│  │  (AI处理引擎)        │            │  (渠道管理器)        │            │
│  └─────────────────────┘            └──────────┬──────────┘            │
│                                                │                        │
│              ┌─────────────────────────────────┼───────────────────┐   │
│              │                                 │                   │   │
│              ▼                                 ▼                   ▼   │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐  ...      │
│  │ TelegramChannel│  │ WhatsAppChannel│  │ DiscordChannel │           │
│  └────────────────┘  └───────┬────────┘  └────────────────┘           │
│                              │                                         │
└──────────────────────────────┼─────────────────────────────────────────┘
                               │ WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Bridge (Node.js + TypeScript)                      │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                 BridgeServer (WebSocket)                         │   │
│  │                 ws://127.0.0.1:端口                              │   │
│  └─────────────────────────────┬───────────────────────────────────┘   │
│                                │                                        │
│                                ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                WhatsAppClient (Baileys)                          │   │
│  │                  WhatsApp Web 协议实现                            │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 一、前端到后端的通信

### 1.1 双路径通信机制

前端根据运行环境选择不同的通信方式：

| 环境 | 通信方式 | 说明 |
|------|----------|------|
| 浏览器环境 | HTTP REST API | 直接使用 axios 发送请求 |
| Electron 环境 | IPC + HTTP | 通过 Electron IPC 转发请求 |

### 1.2 通信流程

```
Vue App (App.vue)
    ↓ 检测 window.electronAPI 是否存在
    ├── 存在 → Electron 环境
    │     ↓
    │   ipcRenderer.invoke('send-message')  [preload.js]
    │     ↓
    │   Electron Main Process (main.js)
    │     ↓ 使用 node:http 模块
    │   Python API Server (:3000)
    │
    └── 不存在 → 浏览器环境
          ↓
        axios.post(`${API_URL}/chat`)
          ↓
        Python API Server (:3000)
```

### 1.3 关键代码

#### 前端入口 (`frontend/src/App.vue`)

```javascript
async function sendMessage(content) {
  // 优先使用 Electron IPC
  if (window.electronAPI && window.electronAPI.sendMessage) {
    const result = await window.electronAPI.sendMessage(content)
    return result
  }

  // 使用 axios 发送 HTTP POST 请求
  try {
    const response = await axios.post(`${API_URL}/chat`, {
      message: content
    })
    return response.data
  } catch (error) {
    console.error('发送消息失败:', error)
  }
}
```

#### IPC 桥接 (`frontend/electron/preload.js`)

```javascript
const { contextBridge, ipcRenderer } = require('electron')

// 通过 contextBridge 安全地暴露 API 给渲染进程
contextBridge.exposeInMainWorld('electronAPI', {
  sendMessage: (message) => ipcRenderer.invoke('send-message', message),
  // ... 其他 API
})
```

#### Electron 主进程 (`frontend/electron/main.js`)

```javascript
const { app, BrowserWindow, ipcMain } = require('electron')
const http = require('http')

// 处理来自渲染进程的 IPC 请求
ipcMain.handle('send-message', async (event, message) => {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: '127.0.0.1',
      port: 3000,
      path: '/chat',
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      }
    }

    const req = http.request(options, (res) => {
      let data = ''
      res.on('data', chunk => data += chunk)
      res.on('end', () => resolve(JSON.parse(data)))
    })

    req.on('error', reject)
    req.write(JSON.stringify({ message }))
    req.end()
  })
})
```

---

## 二、后端 HTTP API

### 2.1 API 服务器配置

| 配置项 | 值 |
|--------|-----|
| 主机 | `127.0.0.1` |
| 端口 | `3000` |
| 框架 | aiohttp |

### 2.2 API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/chat` | 标准聊天请求，返回 JSON 响应 |
| GET | `/chat/stream` | SSE 流式响应 |
| OPTIONS | `*` | CORS 预检请求处理 |

### 2.3 后端 API 代码 (`backend/desktopclaw/api/server.py`)

```python
from aiohttp import web
import json

class APIServer:
    def __init__(self, host='127.0.0.1', port=3000):
        self.host = host
        self.port = port
        self.app = web.Application()
        self._setup_routes()

    def _setup_routes(self):
        self.app.router.add_post('/chat', self.handle_chat)
        self.app.router.add_get('/chat/stream', self.handle_stream)
        self.app.router.add_options('/{path:.*}', self.handle_options)

    async def handle_chat(self, request):
        """处理标准聊天请求"""
        data = await request.json()
        message = data.get('message', '')

        # 将消息放入消息总线
        # ... 处理逻辑

        return web.json_response({
            'status': 'success',
            'response': '...'
        })

    async def handle_stream(self, request):
        """处理 SSE 流式响应"""
        response = web.StreamResponse()
        response.headers['Content-Type'] = 'text/event-stream'
        await response.prepare(request)

        # 流式发送数据
        async for chunk in self.generate_response():
            await response.write(f"data: {chunk}\n\n".encode())

        return response

    async def handle_options(self, request):
        """处理 CORS 预检请求"""
        response = web.Response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
```

---

## 三、后端内部消息总线

### 3.1 消息总线架构

后端使用异步消息总线解耦各组件：

```python
# backend/desktopclaw/bus/queue.py
import asyncio

class MessageBus:
    def __init__(self):
        # 入站消息队列 (渠道 -> 代理)
        self.inbound: asyncio.Queue[InboundMessage] = asyncio.Queue()
        # 出站消息队列 (代理 -> 渠道)
        self.outbound: asyncio.Queue[OutboundMessage] = asyncio.Queue()
```

### 3.2 消息事件类型

```python
# backend/desktopclaw/bus/events.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class InboundMessage:
    """入站消息 - 从渠道接收"""
    channel: str           # 来源渠道
    user_id: str          # 用户标识
    content: str          # 消息内容
    metadata: dict        # 元数据

@dataclass
class OutboundMessage:
    """出站消息 - 发送到渠道"""
    channel: str           # 目标渠道
    user_id: str          # 用户标识
    content: str          # 消息内容
    metadata: dict        # 元数据
```

### 3.3 消息流转

```
外部渠道 (Telegram/WhatsApp/Discord)
        ↓
   ChannelAdapter (接收消息)
        ↓
   inbound Queue
        ↓
   AgentLoop (AI处理)
        ↓
   outbound Queue
        ↓
   ChannelAdapter (发送消息)
        ↓
外部渠道
```

---

## 四、渠道适配器

### 4.1 基类定义 (`backend/desktopclaw/channels/base.py`)

```python
from abc import ABC, abstractmethod

class BaseChannel(ABC):
    """渠道适配器基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """渠道名称"""
        pass

    @abstractmethod
    async def start(self):
        """启动渠道"""
        pass

    @abstractmethod
    async def stop(self):
        """停止渠道"""
        pass

    @abstractmethod
    async def send_message(self, user_id: str, content: str):
        """发送消息"""
        pass

    @abstractmethod
    async def receive_message(self) -> InboundMessage:
        """接收消息"""
        pass
```

### 4.2 WhatsApp 渠道实现

WhatsApp 渠道通过 WebSocket 与 Node.js Bridge 通信：

```python
# backend/desktopclaw/channels/whatsapp.py
import websockets
import json

class WhatsAppChannel(BaseChannel):
    name = "whatsapp"

    async def start(self):
        bridge_url = "ws://127.0.0.1:8080"
        async with websockets.connect(bridge_url) as ws:
            # 发送认证
            await ws.send(json.dumps({
                "type": "auth",
                "token": self.token
            }))

            # 监听消息
            async for message in ws:
                await self._handle_bridge_message(message)

    async def send_message(self, user_id: str, content: str):
        await self.ws.send(json.dumps({
            "type": "send",
            "user_id": user_id,
            "content": content
        }))
```

---

## 五、Bridge 服务

### 5.1 Bridge 架构

Bridge 是一个 Node.js 服务，负责：
- 作为 WebSocket 服务器接受 Python 后端连接
- 实现第三方平台协议（如 WhatsApp Web）

```
Python Backend (WebSocket Client)
        ↓
Bridge Server (WebSocket Server)
        ↓
WhatsApp Client (Baileys)
        ↓
WhatsApp Servers
```

### 5.2 Bridge 服务代码 (`backend/bridge/src/server.ts`)

```typescript
import { WebSocketServer, WebSocket } from 'ws'

class BridgeServer {
  private wss: WebSocketServer
  private clients: Set<WebSocket> = new Set()

  constructor(port: number) {
    this.wss = new WebSocketServer({
      host: '127.0.0.1',
      port: port
    })

    this.wss.on('connection', (ws) => {
      this.clients.add(ws)

      ws.on('message', (data) => {
        this.handleMessage(ws, data)
      })

      ws.on('close', () => {
        this.clients.delete(ws)
      })
    })
  }

  private handleMessage(ws: WebSocket, data: Buffer) {
    const message = JSON.parse(data.toString())

    switch (message.type) {
      case 'auth':
        this.handleAuth(ws, message.token)
        break
      case 'send':
        this.handleSend(message)
        break
    }
  }
}
```

---

## 六、启动流程

### 6.1 启动命令

```bash
# 1. 启动后端 Gateway (API 服务器在端口 3000)
desktopclaw gateway --port 3000

# 2. 启动前端开发模式
cd frontend
npm run electron:dev
```

### 6.2 启动顺序

1. **后端服务** - Python API Server 监听 `127.0.0.1:3000`
2. **Bridge 服务** - Node.js WebSocket Server (可选，用于第三方渠道)
3. **前端应用** - Electron 应用启动，加载 Vue 界面

---

## 七、核心文件索引

| 层级 | 文件路径 | 作用 |
|------|----------|------|
| 前端入口 | `frontend/src/App.vue` | 消息发送逻辑 |
| IPC 桥接 | `frontend/electron/preload.js` | contextBridge 暴露 API |
| 主进程 | `frontend/electron/main.js` | IPC 处理 + HTTP 转发 |
| 后端 API | `backend/desktopclaw/api/server.py` | HTTP 路由处理 |
| 消息总线 | `backend/desktopclaw/bus/queue.py` | 异步消息队列 |
| 事件定义 | `backend/desktopclaw/bus/events.py` | 消息数据结构 |
| 渠道基类 | `backend/desktopclaw/channels/base.py` | 抽象接口定义 |
| 渠道管理器 | `backend/desktopclaw/channels/manager.py` | 消息路由分发 |
| WhatsApp 渠道 | `backend/desktopclaw/channels/whatsapp.py` | WebSocket 客户端 |
| Agent 引擎 | `backend/desktopclaw/agent/loop.py` | AI 消息处理核心 |
| CLI 入口 | `backend/desktopclaw/cli/commands.py` | 命令行入口 |
| Bridge 服务器 | `backend/bridge/src/server.ts` | WebSocket 服务器 |
| WhatsApp 客户端 | `backend/bridge/src/whatsapp.ts` | Baileys 协议实现 |

---

## 八、通信方式总结

| 通信场景 | 通信方式 | 协议 |
|----------|----------|------|
| Vue → Electron Main | IPC | Electron IPC |
| Electron Main → Python Backend | HTTP | HTTP/1.1 |
| 浏览器 → Python Backend | HTTP | HTTP/1.1 |
| Python Backend → Bridge | WebSocket | WebSocket |
| Bridge → WhatsApp | Baileys | WhatsApp Web Protocol |
| 后端内部组件 | asyncio.Queue | 内存队列 |