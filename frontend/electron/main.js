const { app, BrowserWindow, ipcMain, screen } = require('electron')
const path = require('path')
const fs = require('fs')
const http = require('http')
const { spawn, execSync } = require('child_process')

const isDev = process.env.NODE_ENV === 'development' || process.argv.includes('--dev')
const forcePickUi = process.argv.includes('--pick-ui')

app.commandLine.appendSwitch('disable-gpu-shader-disk-cache')
if (isDev) {
    app.setPath('userData', path.join(app.getPath('appData'), 'DesktopClaw-dev'))
}

let launcherWin = null
let petWin = null
let chatWin = null
let feishuSSEController = null
let backendProcess = null
let displayListenersRegistered = false

const UI_PREF_FILE = () => path.join(app.getPath('userData'), 'ui-preference.json')
const CHAT_STATE_FILE = () => path.join(app.getPath('userData'), 'chat-state.json')

const getResourcePath = (relativePath) => {
    if (isDev) {
        return path.join(__dirname, '..', relativePath)
    }
    return path.join(process.resourcesPath, relativePath)
}

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

function readUiPreference() {
    try {
        const raw = fs.readFileSync(UI_PREF_FILE(), 'utf8')
        const parsed = JSON.parse(raw)
        if (parsed.mode === 'pet' || parsed.mode === 'chat') {
            return {
                mode: parsed.mode,
                skipLauncher: !!parsed.skipLauncher,
            }
        }
    } catch {}
    return null
}

function writeUiPreference(mode, remember) {
    if (!remember) return
    try {
        fs.mkdirSync(path.dirname(UI_PREF_FILE()), { recursive: true })
        fs.writeFileSync(
            UI_PREF_FILE(),
            JSON.stringify({ mode, skipLauncher: true }, null, 2),
            'utf8',
        )
    } catch (err) {
        console.error('[Electron] Failed to write UI preference:', err)
    }
}

function readChatState() {
    try {
        const raw = fs.readFileSync(CHAT_STATE_FILE(), 'utf8')
        return JSON.parse(raw)
    } catch {
        return null
    }
}

function writeChatState(payload) {
    try {
        fs.mkdirSync(path.dirname(CHAT_STATE_FILE()), { recursive: true })
        fs.writeFileSync(CHAT_STATE_FILE(), JSON.stringify(payload, null, 2), 'utf8')
    } catch (err) {
        console.error('[Electron] Failed to write chat state:', err)
    }
}

function broadcastChatState(payload) {
    const targets = [petWin, chatWin].filter((w) => w && !w.isDestroyed())
    for (const win of targets) {
        win.webContents.send('chat-state-updated', payload)
    }
}

function getWebPreferences() {
    return {
        preload: path.resolve(__dirname, 'preload.js'),
        devTools: isDev,
        contextIsolation: true,
        nodeIntegration: false,
    }
}

function applyCsp(win) {
    win.webContents.session.webRequest.onHeadersReceived((details, callback) => {
        callback({
            responseHeaders: {
                ...details.responseHeaders,
                'Content-Security-Policy': [
                    "default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; media-src 'self' blob: http://127.0.0.1:3000 https://127.0.0.1:3000; connect-src 'self' blob: http://127.0.0.1:3000 https://127.0.0.1:3000 ws://localhost:5173 wss://localhost:5173;",
                ],
            },
        })
    })
}

function attachConsoleForward(win) {
    win.webContents.on('console-message', (_event, _level, message) => {
        if (message.includes('[Frontend]')) {
            console.log('[Renderer]', message)
        }
    })
}

function loadAppUrl(win, mode) {
    if (isDev) {
        const vitePort = process.env.VITE_PORT || '5173'
        win.loadURL(`http://localhost:${vitePort}/?mode=${mode}`)
    } else {
        win.loadFile(path.join(getResourcePath('dist'), 'index.html'), {
            query: { mode },
        })
    }
}

function notifyScreenInfoUpdated() {
    const data = getScreenInfoData()
    if (petWin && !petWin.isDestroyed()) {
        petWin.webContents.send('screen-info-updated', data)
    }
}

function registerDisplayListeners() {
    if (displayListenersRegistered) return
    displayListenersRegistered = true
    screen.on('display-added', notifyScreenInfoUpdated)
    screen.on('display-removed', notifyScreenInfoUpdated)
    screen.on('display-metrics-changed', notifyScreenInfoUpdated)
}

const startBackend = () => {
    return new Promise((resolve, reject) => {
        let backendPath
        let args
        let cwd

        if (isDev) {
            const backendDir = path.join(__dirname, '..', '..', 'backend')
            backendPath = 'python'
            args = ['-m', 'desktopclaw', 'api', '--port', '3000']
            cwd = backendDir
        } else {
            backendPath = path.join(getResourcePath('backend'), 'desktopclaw.exe')
            args = ['api', '--port', '3000']
            cwd = undefined
        }

        const backendDir = isDev ? path.join(__dirname, '..', '..', 'backend') : null

        console.log('[Electron] Starting backend:', backendPath, args, 'cwd:', cwd)

        backendProcess = spawn(backendPath, args, {
            detached: false,
            cwd,
            stdio: ['ignore', 'pipe', 'pipe'],
            shell: true,
            env: {
                ...process.env,
                PYTHONIOENCODING: 'utf-8',
                LANG: 'en_US.UTF-8',
                ...(backendDir ? { PYTHONPATH: backendDir } : {}),
            },
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
                method: 'GET',
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

function getScreenInfoData() {
    const displays = screen.getAllDisplays()
    const primary = screen.getPrimaryDisplay()
    return {
        displays: displays.map((d) => ({
            id: d.id,
            bounds: d.bounds,
            workArea: d.workArea,
            scaleFactor: d.scaleFactor,
            isPrimary: d.id === primary.id,
            rotation: d.rotation,
            internal: d.internal,
        })),
        primaryScaleFactor: primary.scaleFactor,
    }
}

function createLauncherWindow() {
    if (launcherWin && !launcherWin.isDestroyed()) return launcherWin

    launcherWin = new BrowserWindow({
        width: 520,
        height: 400,
        center: true,
        transparent: false,
        frame: true,
        resizable: false,
        title: 'DesktopClaw',
        autoHideMenuBar: true,
        webPreferences: getWebPreferences(),
    })

    attachConsoleForward(launcherWin)
    applyCsp(launcherWin)
    loadAppUrl(launcherWin, 'launcher')

    launcherWin.on('closed', () => {
        launcherWin = null
    })

    return launcherWin
}

function createPetWindow() {
    if (petWin && !petWin.isDestroyed()) {
        petWin.focus()
        return petWin
    }

    const primary = screen.getPrimaryDisplay()
    const workArea = primary.workArea
    const petW = 360
    const petH = 400
    const initX = workArea.x + workArea.width - petW - 50
    const initY = workArea.y + workArea.height - petH - 50

    console.log('[Electron] Creating pet window at:', initX, initY, 'size:', petW, petH)

    petWin = new BrowserWindow({
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
        webPreferences: getWebPreferences(),
    })

    attachConsoleForward(petWin)
    applyCsp(petWin)
    loadAppUrl(petWin, 'pet')
    registerDisplayListeners()

    petWin.on('closed', () => {
        petWin = null
    })

    return petWin
}

function createChatWindow() {
    if (chatWin && !chatWin.isDestroyed()) {
        chatWin.focus()
        return chatWin
    }

    chatWin = new BrowserWindow({
        width: 1000,
        height: 700,
        minWidth: 800,
        minHeight: 600,
        center: true,
        transparent: false,
        frame: true,
        resizable: true,
        title: 'DesktopClaw Chat',
        autoHideMenuBar: true,
        webPreferences: getWebPreferences(),
    })

    attachConsoleForward(chatWin)
    applyCsp(chatWin)
    loadAppUrl(chatWin, 'chat')

    chatWin.on('closed', () => {
        chatWin = null
    })

    return chatWin
}

function closeLauncherWindow() {
    if (launcherWin && !launcherWin.isDestroyed()) {
        launcherWin.close()
    }
    launcherWin = null
}

function openUiMode(mode) {
    if (mode === 'pet') {
        createPetWindow()
    } else if (mode === 'chat') {
        createChatWindow()
    }
}

function openInitialWindow() {
    const pref = readUiPreference()
    if (pref && pref.skipLauncher && !forcePickUi) {
        openUiMode(pref.mode)
    } else {
        createLauncherWindow()
    }
}

app.on('ready', () => {
    openInitialWindow()
    console.log('[Electron] Starting backend service...')
    startBackend()
        .then(() => console.log('[Electron] Backend started successfully'))
        .catch((err) => console.error('[Electron] Failed to start backend:', err))
})

app.on('will-quit', () => {
    if (backendProcess) {
        console.log('[Electron] Killing backend process tree (will-quit)...')
        killProcessTree(backendProcess)
        backendProcess = null
    }
})

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        openInitialWindow()
    }
})

ipcMain.handle('launch-ui', (_event, { mode, remember }) => {
    if (mode !== 'pet' && mode !== 'chat') {
        return { success: false, error: 'invalid mode' }
    }
    writeUiPreference(mode, remember)
    closeLauncherWindow()
    openUiMode(mode)
    return { success: true }
})

ipcMain.handle('get-ui-preference', () => readUiPreference())

ipcMain.handle('sync-chat-state', (_event, payload) => {
    if (payload && typeof payload === 'object') {
        writeChatState(payload)
        broadcastChatState(payload)
    }
    return { success: true }
})

ipcMain.handle('get-chat-state', () => readChatState())

ipcMain.handle('switch-ui-mode', (_event, mode) => {
    if (mode !== 'pet' && mode !== 'chat') {
        return { success: false, error: 'invalid mode' }
    }
    if (mode === 'pet') {
        if (chatWin && !chatWin.isDestroyed()) chatWin.close()
        createPetWindow()
    } else {
        if (petWin && !petWin.isDestroyed()) petWin.close()
        createChatWindow()
    }
    return { success: true }
})

ipcMain.handle('close-chat-window', () => {
    if (chatWin && !chatWin.isDestroyed()) {
        chatWin.close()
    }
    return { success: true }
})

ipcMain.handle('close-window', () => {
    console.log('[Electron] Close requested from frontend, shutting down all processes...')
    if (backendProcess) {
        console.log('[Electron] Killing backend process tree (close-window)...')
        killProcessTree(backendProcess)
        backendProcess = null
    }
    app.exit(0)
})

ipcMain.handle('set-ignore-mouse-events', (_event, ignore, options) => {
    if (petWin && !petWin.isDestroyed()) {
        petWin.setIgnoreMouseEvents(ignore, options)
    }
})

ipcMain.handle('resize-pet-window', (_event, x, y, width, height) => {
    if (petWin && !petWin.isDestroyed()) {
        petWin.setBounds({
            x: Math.round(x),
            y: Math.round(y),
            width: Math.max(Math.round(width), 120),
            height: Math.max(Math.round(height), 120),
        })
    }
})

ipcMain.handle('move-pet-window', (_event, x, y) => {
    if (petWin && !petWin.isDestroyed()) {
        petWin.setPosition(Math.round(x), Math.round(y))
    }
})

ipcMain.handle('get-window-position', () => {
    if (petWin && !petWin.isDestroyed()) {
        const bounds = petWin.getBounds()
        return { x: bounds.x, y: bounds.y }
    }
    return { x: 0, y: 0 }
})

ipcMain.handle('send-message', async (_event, message, options = {}) => {
    return new Promise((resolve, reject) => {
        const body = { message, ...options }
        const data = JSON.stringify(body)

        const headers = {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(data),
        }

        if (options.apiKey) {
            headers.Authorization = `Bearer ${options.apiKey}`
        }

        const reqOptions = {
            hostname: '127.0.0.1',
            port: 3000,
            path: '/chat',
            method: 'POST',
            headers,
        }

        const req = http.request(reqOptions, (res) => {
            let responseData = ''

            res.on('data', (chunk) => {
                responseData += chunk
            })

            res.on('end', () => {
                try {
                    resolve(JSON.parse(responseData))
                } catch (e) {
                    reject(new Error('Invalid JSON response: ' + responseData))
                }
            })
        })

        req.on('error', (error) => {
            reject(error)
        })

        req.write(data)
        req.end()
    })
})

ipcMain.handle('connect-feishu-sse', async () => {
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
            signal: feishuSSEController.signal,
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
                            if (petWin && !petWin.isDestroyed()) {
                                petWin.webContents.send('feishu-event', data)
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

ipcMain.handle('disconnect-feishu-sse', async () => {
    if (feishuSSEController) {
        feishuSSEController.abort()
        feishuSSEController = null
        console.log('[Electron] Feishu SSE disconnected')
    }
    return { success: true }
})

ipcMain.handle('scan-live2d-models', async () => {
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
            const modelFile = files.find((f) => f.endsWith('.model3.json'))

            if (modelFile) {
                models.push({
                    name: entry.name,
                    path: `/${entry.name}/${modelFile}`,
                })
            }
        }

        console.log(`[Electron] Found ${models.length} Live2D models`)
        return { success: true, models }
    } catch (error) {
        console.error('[Electron] Failed to scan Live2D models:', error)
        return { success: false, error: error.message, models: [] }
    }
})

ipcMain.handle('get-screen-info', () => getScreenInfoData())
