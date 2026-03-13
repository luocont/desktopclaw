const { spawn } = require('child_process');
const waitOn = require('wait-on');

// 启动 Vite 开发服务器
const vite = spawn('npm', ['run', 'dev'], {
  stdio: 'inherit',
  shell: true
});

// 等待 Vite 服务器启动
waitOn({
  resources: ['http://localhost:5173'],
  timeout: 30000
}).then(() => {
  console.log('Vite server ready, starting Electron...');

  // 启动 Electron
  const electron = spawn('electron', ['.', '--dev'], {
    stdio: 'inherit',
    shell: true
  });

  electron.on('close', (code) => {
    console.log(`Electron exited with code ${code}`);
    vite.kill();
    process.exit(code);
  });
}).catch((err) => {
  console.error('Failed to start:', err);
  vite.kill();
  process.exit(1);
});

// 处理 Ctrl+C
process.on('SIGINT', () => {
  vite.kill();
  process.exit(0);
});
