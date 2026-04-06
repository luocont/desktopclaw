const {app,BrowserWindow,ipcMain,shell} = require('electron')
const path = require('path')
const fs = require('fs')
const http = require('http')

// 检测是否在开发模式：检查是否有 VITE 开发服务器运行，或通过环境变量
const isDev = process.env.NODE_ENV === 'development' || process.argv.includes('--dev')

let win
let feishuSSEController = null

const createWindow = () => {
    if(win)return
    const { width: screenWidth, height: screenHeight } = require('electron').screen.getPrimaryDisplay().workAreaSize
        win = new BrowserWindow({
        width: screenWidth,
        height: screenHeight,
        x: 0,
        y: 0,
        transparent: true,
        frame: false,
        alwaysOnTop: true,
        resizable: false,
        skipTaskbar: true,
        autoHideMenuBar: true,
        webPreferences: {
            preload:path.resolve(__dirname,'preload.js'),
            devTools: isDev,
            contextIsolation: true,
            nodeIntegration: false
        }
    })
    
    // 修改 CSP 以允许加载本地媒体文件和连接后端
    win.webContents.session.webRequest.onHeadersReceived((details, callback) => {
        callback({
            responseHeaders: {
                ...details.responseHeaders,
                'Content-Security-Policy': ["default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; media-src 'self' blob: http://127.0.0.1:3000 https://127.0.0.1:3000; connect-src 'self' blob: http://127.0.0.1:3000 https://127.0.0.1:3000 ws://localhost:5173 wss://localhost:5173;"]
            }
        })
    })
    
    //win.loadFile('../index.html')
    if (isDev) {
        win.loadURL('http://localhost:5173')
        // 如需调试可取消下面这行注释：
        // win.webContents.openDevTools()
      } else {
        win.loadFile(path.join(__dirname, '../dist/index.html'))
      }
}

app.on('ready', () => {
    createWindow()
})

app.on('window-all-closed',() => {
    if(process.platform !== 'darwin')app.quit()
})

app.on('activate',()=>{
    if(BrowserWindow.getAllWindows().length === 0)createWindow()
})

// IPC handler for setting ignore mouse events (click-through)
ipcMain.handle('set-ignore-mouse-events', (event, ignore, options) => {
    if (win && !win.isDestroyed()) {
        win.setIgnoreMouseEvents(ignore, options)
    }
})

// IPC handler for sending messages to backend
ipcMain.handle('send-message', async (event, message, channel = 'feishu') => {
    return new Promise((resolve, reject) => {
        const data = JSON.stringify({ message, channel });

        const options = {
            hostname: '127.0.0.1',
            port: 3000,
            path: '/chat',
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Content-Length': Buffer.byteLength(data)
            }
        };

        const req = http.request(options, (res) => {
            let responseData = '';

            res.on('data', (chunk) => {
                responseData += chunk;
            });

            res.on('end', () => {
                try {
                    const parsed = JSON.parse(responseData);
                    resolve(parsed);
                } catch (e) {
                    reject(new Error('Invalid JSON response: ' + responseData));
                }
            });
        });

        req.on('error', (error) => {
            reject(error);
        });

        req.write(data);
        req.end();
    });
})

// IPC handler for connecting to Feishu SSE
ipcMain.handle('connect-feishu-sse', async (event) => {
    // 断开之前的连接
    if (feishuSSEController) {
        feishuSSEController.abort()
        feishuSSEController = null
    }

    return new Promise((resolve, reject) => {
        feishuSSEController = new AbortController()
        
        const options = {
            hostname: '127.0.0.1',
            port: 3000,
            path: '/feishu/events',
            method: 'GET',
            signal: feishuSSEController.signal
        }

        const req = http.request(options, (res) => {
            console.log('[Electron] Feishu SSE connected')
            resolve({ success: true })

            let buffer = ''
            res.on('data', (chunk) => {
                buffer += chunk.toString()
                const lines = buffer.split('\n\n')
                buffer = lines.pop() || ''

                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6))
                            // 发送事件到渲染进程
                            if (win && !win.isDestroyed()) {
                                win.webContents.send('feishu-event', data)
                            }
                        } catch (e) {
                            console.error('[Electron] Failed to parse SSE data:', e)
                        }
                    }
                }
            })

            res.on('end', () => {
                console.log('[Electron] Feishu SSE connection ended')
                feishuSSEController = null
            })

            res.on('error', (error) => {
                console.error('[Electron] Feishu SSE error:', error)
                feishuSSEController = null
            })
        })

        req.on('error', (error) => {
            if (error.name !== 'AbortError') {
                console.error('[Electron] Feishu SSE request error:', error)
                reject(error)
            }
        })

        req.end()
    })
})

// IPC handler for disconnecting Feishu SSE
ipcMain.handle('disconnect-feishu-sse', async (event) => {
    if (feishuSSEController) {
        feishuSSEController.abort()
        feishuSSEController = null
        console.log('[Electron] Feishu SSE disconnected')
    }
    return { success: true }
})

// IPC handler for scanning available Live2D models in public directory
ipcMain.handle('scan-live2d-models', async (event) => {
    const publicDir = path.join(__dirname, '../public')
    
    try {
        if (!fs.existsSync(publicDir)) {
            return { success: false, error: 'public directory not found', models: [] }
        }

        const entries = fs.readdirSync(publicDir, { withFileTypes: true })
        const models = []

        for (const entry of entries) {
            if (!entry.isDirectory()) continue

            const dirPath = path.join(publicDir, entry.name)
            const files = fs.readdirSync(dirPath)
            const modelFile = files.find(f => f.endsWith('.model3.json'))

            if (modelFile) {
                models.push({
                    name: entry.name,
                    path: `/${entry.name}/${modelFile}`
                })
            }
        }

        console.log(`[Electron] Found ${models.length} Live2D models:`, models.map(m => m.name))
        return { success: true, models }

    } catch (error) {
        console.error('[Electron] Failed to scan Live2D models:', error)
        return { success: false, error: error.message, models: [] }
    }
})