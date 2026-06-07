const {app,BrowserWindow,ipcMain,shell,screen} = require('electron')
const path = require('path')
const fs = require('fs')
const http = require('http')
const { spawn, execSync } = require('child_process')

// 检测是否在开发模式：检查是否有 VITE 开发服务器运行，或通过环境变量
const isDev = process.env.NODE_ENV === 'development' || process.argv.includes('--dev')

let win
let feishuSSEController = null
let backendProcess = null

// 获取资源路径，兼容开发和生产模式
const getResourcePath = (relativePath) => {
    if (isDev) {
        return path.join(__dirname, '..', relativePath)
    } else {
        return path.join(process.resourcesPath, relativePath)
    }
}

// 递归杀死进程树（Windows 用 taskkill /t，Unix 用 SIGTERM）
function killProcessTree(proc) {
    if (!proc || !proc.pid) return
    try {
        if (process.platform === 'win32') {
            execSync(`taskkill /f /t /pid ${proc.pid}`, { stdio: 'ignore', timeout: 3000 })
        } else {
            proc.kill('SIGTERM')
        }
    } catch {}
}

const startBackend = () => {
    return new Promise((resolve, reject) => {
        let backendPath
        let args
        let cwd
        
        if (isDev) {
            backendPath = 'python'
            args = ['-m', 'desktopclaw', 'api', '--port', '3000']
            cwd = path.join(__dirname, '..', '..')
        } else {
            backendPath = path.join(getResourcePath('backend'), 'desktopclaw.exe')
            args = []
            cwd = undefined
        }

        console.log('[Electron] Starting backend:', backendPath, args, 'cwd:', cwd)

        backendProcess = spawn(backendPath, args, {
            detached: false,
            cwd: cwd,
            stdio: ['ignore', 'pipe', 'pipe'],
            shell: true,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8', LANG: 'en_US.UTF-8' }
        })

        backendProcess.stdout.on('data', (data) => {
            process.stdout.write(Buffer.from(`[Backend] ${data.toString('utf8').trim()}\n`, 'utf8'))
        })

        backendProcess.stderr.on('data', (data) => {
            process.stdout.write(Buffer.from(`[Backend Error] ${data.toString('utf8').trim()}\n`, 'utf8'))
        })

        backendProcess.on('close', (code) => {
            console.log('[Electron] Backend process closed with code:', code)
            backendProcess = null
        })

        backendProcess.on('error', (err) => {
            console.error('[Electron] Failed to start backend:', err)
            reject(err)
        })

        const checkBackendReady = (attempt) => {
            if (attempt > 60) {
                reject(new Error('Backend failed to start within 60 seconds'))
                return
            }

            const req = http.request({
                hostname: '127.0.0.1',
                port: 3000,
                path: '/health',
                method: 'GET'
            }, (res) => {
                if (res.statusCode === 200) {
                    console.log('[Electron] Backend is ready')
                    resolve()
                } else {
                    setTimeout(() => checkBackendReady(attempt + 1), 1000)
                }
            })

            req.on('error', () => {
                setTimeout(() => checkBackendReady(attempt + 1), 1000)
            })

            req.end()
        }

        setTimeout(() => checkBackendReady(0), 2000)
    })
}

// 计算所有显示器的联合边界
function getDisplaysUnionBounds() {
    const displays = screen.getAllDisplays()
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
    for (const d of displays) {
        const b = d.bounds
        console.log('[Electron] Display:', d.id, 'bounds:', JSON.stringify(b), 'workArea:', JSON.stringify(d.workArea), 'scaleFactor:', d.scaleFactor)
        minX = Math.min(minX, b.x)
        minY = Math.min(minY, b.y)
        maxX = Math.max(maxX, b.x + b.width)
        maxY = Math.max(maxY, b.y + b.height)
    }
    return { x: minX, y: minY, width: maxX - minX, height: maxY - minY }
}

// 获取屏幕信息数据
function getScreenInfoData() {
    const displays = screen.getAllDisplays()
    const primary = screen.getPrimaryDisplay()
    return {
        displays: displays.map(d => ({
            id: d.id,
            bounds: d.bounds,
            workArea: d.workArea,
            scaleFactor: d.scaleFactor,
            isPrimary: d.id === primary.id,
            rotation: d.rotation,
            internal: d.internal
        })),
        primaryScaleFactor: primary.scaleFactor
    }
}

const createWindow = () => {
    if(win)return
    // 获取主显示器信息，用于初始窗口位置
    const primary = screen.getPrimaryDisplay()
    const workArea = primary.workArea
    const petW = 300, petH = 400
    // 初始位置：主屏右下角
    const initX = workArea.x + workArea.width - petW - 50
    const initY = workArea.y + workArea.height - petH - 50

    console.log('[Electron] Creating pet window at:', initX, initY, 'size:', petW, petH)

    win = new BrowserWindow({
        width: petW,
        height: petH,
        x: initX,
        y: initY,
        transparent: true,
        frame: false,
        alwaysOnTop: true,
        resizable: true,
        skipTaskbar: true,
        autoHideMenuBar: true,
        webPreferences: {
            preload:path.resolve(__dirname,'preload.js'),
            devTools: isDev,
            contextIsolation: true,
            nodeIntegration: false
        }
    })

    // 捕获渲染进程的 console.log
    win.webContents.on('console-message', (event, level, message) => {
        if (message.includes('[Frontend]')) {
            console.log('[Renderer]', message)
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
        const vitePort = process.env.VITE_PORT || '5173'
        win.loadURL(`http://localhost:${vitePort}`)
      } else {
        win.loadFile(path.join(getResourcePath('dist'), 'index.html'))
      }

    // 监听显示器变化
    screen.on('display-added', () => {
        // 通知前端屏幕信息已更新
        if (win && !win.isDestroyed()) {
            win.webContents.send('screen-info-updated', getScreenInfoData())
        }
    })
    screen.on('display-removed', () => {
        if (win && !win.isDestroyed()) {
            win.webContents.send('screen-info-updated', getScreenInfoData())
        }
    })
    screen.on('display-metrics-changed', () => {
        if (win && !win.isDestroyed()) {
            win.webContents.send('screen-info-updated', getScreenInfoData())
        }
    })
}

app.on('ready', async () => {
    try {
        console.log('[Electron] Starting backend service...')
        await startBackend()
        console.log('[Electron] Backend started successfully')
    } catch (err) {
        console.error('[Electron] Failed to start backend:', err)
    }
    createWindow()
})

// will-quit 在 app.exit(0) 时触发，确保后端进程被杀死
app.on('will-quit', () => {
    if (backendProcess) {
        console.log('[Electron] Killing backend process tree (will-quit)...')
        killProcessTree(backendProcess)
        backendProcess = null
    }
})

app.on('window-all-closed',() => {
    if(process.platform !== 'darwin')app.quit()
})

app.on('activate',()=>{
    if(BrowserWindow.getAllWindows().length === 0)createWindow()
})

// IPC handler: 前端点击"退出桌宠"后关闭整个应用
ipcMain.handle('close-window', () => {
    console.log('[Electron] Close requested from frontend, shutting down all processes...')
    // app.exit() 不会触发 will-quit，必须在此先杀后端再退出
    if (backendProcess) {
        console.log('[Electron] Killing backend process tree (close-window)...')
        killProcessTree(backendProcess)
        backendProcess = null
    }
    app.exit(0)
})

// IPC handler for setting ignore mouse events (click-through)
ipcMain.handle('set-ignore-mouse-events', (event, ignore, options) => {
    if (win && !win.isDestroyed()) {
        win.setIgnoreMouseEvents(ignore, options)
    }
})

// IPC handler for resizing and positioning the pet window
ipcMain.handle('resize-pet-window', (event, x, y, width, height) => {
    if (win && !win.isDestroyed()) {
        win.setBounds({ x: Math.round(x), y: Math.round(y), width: Math.round(width), height: Math.round(height) })
    }
})

// IPC handler for moving the pet window (drag)
ipcMain.handle('move-pet-window', (event, x, y) => {
    if (win && !win.isDestroyed()) {
        win.setPosition(Math.round(x), Math.round(y))
    }
})

// IPC handler for getting current window position
ipcMain.handle('get-window-position', () => {
    if (win && !win.isDestroyed()) {
        const bounds = win.getBounds()
        return { x: bounds.x, y: bounds.y }
    }
    return { x: 0, y: 0 }
})

// IPC handler for sending messages to backend
ipcMain.handle('send-message', async (event, message, options = {}) => {
    return new Promise((resolve, reject) => {
        const body = { message, ...options };
        const data = JSON.stringify(body);

        const headers = {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(data)
        };

        if (options.apiKey) {
            headers['Authorization'] = `Bearer ${options.apiKey}`;
        }

        const reqOptions = {
            hostname: '127.0.0.1',
            port: 3000,
            path: '/chat',
            method: 'POST',
            headers
        };

        const req = http.request(reqOptions, (res) => {
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
    const publicDir = getResourcePath('public')
    
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

        const modelNames = models.map(m => m.name)
        console.log(`[Electron] Found ${models.length} Live2D models`)
        for (const name of modelNames) {
            process.stdout.write(Buffer.from(`  - ${name}\n`, 'utf8'))
        }
        return { success: true, models }

    } catch (error) {
        console.error('[Electron] Failed to scan Live2D models:', error)
        return { success: false, error: error.message, models: [] }
    }
})

// IPC handler: 获取多屏幕信息
ipcMain.handle('get-screen-info', () => {
    return getScreenInfoData()
})
