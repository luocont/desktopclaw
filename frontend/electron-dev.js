const { spawn } = require('child_process');
const http = require('http');

function checkPort(port) {
  return new Promise((resolve) => {
    const req = http.request({
      hostname: 'localhost',
      port: port,
      path: '/',
      method: 'GET',
      timeout: 2000
    }, (res) => {
      resolve(true);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
    req.end();
  });
}

async function waitForVite(maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    for (const port of [5173, 5174, 5175, 5176]) {
      const ok = await checkPort(port);
      if (ok) return port;
    }
    await new Promise(r => setTimeout(r, 1000));
  }
  throw new Error('Vite server did not start within 30 seconds');
}

const vite = spawn('npm', ['run', 'dev'], {
  stdio: 'inherit',
  shell: true
});

waitForVite().then((port) => {
  console.log(`Vite server ready on port ${port}, starting Electron...`);

  const electron = spawn('electron', ['.', '--dev'], {
    stdio: 'inherit',
    shell: true,
    env: { ...process.env, VITE_PORT: port }
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

process.on('SIGINT', () => {
  vite.kill();
  process.exit(0);
});
