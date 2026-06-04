const fs = require('fs');
const path = require('path');

const electronPath = path.dirname(require.resolve('electron'));
const distDir = path.join(__dirname, 'dist');
const backendDir = path.join(__dirname, 'backend', 'desktopclaw');
const appDir = path.join(__dirname, 'app');

console.log('Cleaning existing app directory...');
if (fs.existsSync(appDir)) {
    fs.rmSync(appDir, { recursive: true, force: true });
}

console.log('Creating app directory...');
fs.mkdirSync(appDir, { recursive: true });

console.log('Copying Electron...');
const electronDist = path.join(electronPath, 'dist');
fs.cpSync(electronDist, path.join(appDir, 'electron'), { recursive: true });

console.log('Copying frontend dist...');
const appResourcesDir = path.join(appDir, 'resources', 'app');
fs.mkdirSync(appResourcesDir, { recursive: true });

const distFiles = fs.readdirSync(distDir);
for (const file of distFiles) {
    const srcPath = path.join(distDir, file);
    const destPath = path.join(appResourcesDir, file);
    if (fs.statSync(srcPath).isDirectory()) {
        fs.cpSync(srcPath, destPath, { recursive: true });
    } else {
        fs.copyFileSync(srcPath, destPath);
    }
}

console.log('Copying backend...');
fs.cpSync(backendDir, path.join(appDir, 'backend'), { recursive: true });

console.log('Creating start script...');
const startScript = `@echo off
cd /d "%~dp0"
start /B backend\\desktopclaw.exe
timeout /t 5 /nobreak >nul
electron\\electron.exe resources\\app
`;
fs.writeFileSync(path.join(appDir, 'start.bat'), startScript);

console.log('Creating package.json for Electron...');
const packageJson = {
    name: 'desktopclaw',
    version: '1.0.0',
    main: 'main.js'
};
fs.writeFileSync(path.join(appResourcesDir, 'package.json'), JSON.stringify(packageJson));

console.log('Creating main.js for Electron...');
const mainJs = `const { app, BrowserWindow } = require('electron')
const path = require('path')

let win

const createWindow = () => {
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
            devTools: false,
            contextIsolation: true,
            nodeIntegration: false
        }
    })

    win.loadFile('index.html')

    win.webContents.session.webRequest.onHeadersReceived((details, callback) => {
        callback({
            responseHeaders: {
                ...details.responseHeaders,
                'Content-Security-Policy': ["default-src 'self'; script-src 'self' 'unsafe-inline' 'unsafe-eval'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; media-src 'self' blob: http://127.0.0.1:3000 https://127.0.0.1:3000; connect-src 'self' blob: http://127.0.0.1:3000 https://127.0.0.1:3000;"]
            }
        })
    })
}

app.on('ready', createWindow)

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') app.quit()
})

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
})
`;
fs.writeFileSync(path.join(appResourcesDir, 'main.js'), mainJs);

console.log('App packaged successfully!');
console.log(`App location: ${appDir}`);
