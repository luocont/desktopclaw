const {app,BrowserWindow,ipcMain} = require('electron')
const path = require('path')
const http = require('http')

// 检测是否在开发模式：检查是否有 VITE 开发服务器运行，或通过环境变量
const isDev = process.env.NODE_ENV === 'development' || process.argv.includes('--dev')
let win
const createWindow = () => {
    if(win)return
        win = new BrowserWindow({
        width: 800,
        height: 600,
        autoHideMenuBar: true,
        x: 0,
        y: 0,
        webPreferences: {
            preload:path.resolve(__dirname,'preload.js'),
            devTools: isDev,
            contextIsolation: true,
            nodeIntegration: false
        }
        //alwaysOnTop: true
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

// IPC handler for sending messages to backend
ipcMain.handle('send-message', async (event, message) => {
    return new Promise((resolve, reject) => {
        const data = JSON.stringify({ message });

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