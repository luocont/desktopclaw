const fs = require('fs');
const path = require('path');

const appDir = path.join(__dirname, 'DesktopClaw');

console.log('Cleaning existing app directory...');
if (fs.existsSync(appDir)) {
    fs.rmSync(appDir, { recursive: true, force: true });
}

console.log('Creating app directory...');
fs.mkdirSync(appDir, { recursive: true });

console.log('Copying Electron runtime...');
const electronPath = path.dirname(require.resolve('electron'));
fs.cpSync(path.join(electronPath, 'dist'), path.join(appDir, 'electron'), { recursive: true });

console.log('Copying frontend dist...');
fs.cpSync(path.join(__dirname, 'dist'), path.join(appDir, 'dist'), { recursive: true });

console.log('Copying public folder...');
fs.cpSync(path.join(__dirname, 'public'), path.join(appDir, 'public'), { recursive: true });

console.log('Copying backend...');
fs.cpSync(path.join(__dirname, 'backend', 'desktopclaw'), path.join(appDir, 'backend'), { recursive: true });

console.log('Copying electron folder...');
fs.cpSync(path.join(__dirname, 'electron'), path.join(appDir, 'electron-main'), { recursive: true });

console.log('Creating package.json...');
const packageJson = {
    name: 'desktopclaw',
    version: '1.0.0',
    main: './electron-main/main.js'
};
fs.writeFileSync(path.join(appDir, 'package.json'), JSON.stringify(packageJson));

console.log('Updating main.js backend path...');
const mainJsPath = path.join(appDir, 'electron-main', 'main.js');
let mainJsContent = fs.readFileSync(mainJsPath, 'utf-8');
mainJsContent = mainJsContent.replace(
    "backendPath = path.join(__dirname, '../backend/desktopclaw/desktopclaw.exe')",
    "backendPath = path.join(__dirname, '../backend/desktopclaw.exe')"
);
fs.writeFileSync(mainJsPath, mainJsContent);

console.log('Creating start script...');
const startScript = `@echo off
cd /d "%~dp0"
start /B backend\\desktopclaw.exe
timeout /t 5 /nobreak >nul
electron\\electron.exe .
`;
fs.writeFileSync(path.join(appDir, 'start.bat'), startScript);

console.log('App packaged successfully!');
console.log(`App location: ${appDir}`);
