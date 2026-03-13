const {app,BrowserWindow,ipcMain} = require('electron')
const path = require('path')

const isDev = process.env.NODE_ENV === 'development'
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
        // 打开开发者工具，方便看报错
        win.webContents.openDevTools()
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