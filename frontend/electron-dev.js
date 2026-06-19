const { spawn, execSync } = require('child_process');
const http = require('http');
const fs = require('fs');
const path = require('path');

// 抑制 Node.js 自身 deprecation 警告
process.noDeprecation = true;

// 设置终端输出 UTF-8 编码，避免中文乱码
try { execSync('chcp 65001', { stdio: 'pipe', timeout: 2000 }); } catch {}

// ============================================================
// 启动前清理上次未关闭的进程
// ============================================================

const PORTS_TO_CHECK = [3000, 5173, 5174, 5175, 5176];

/**
 * Windows: 强制杀进程（含子进程树）
 */
function windowsKill(pid) {
  try { execSync(`taskkill /f /t /pid ${pid}`, { stdio: 'ignore', timeout: 5000 }); return true; }
  catch { return false; }
}

/**
 * 通过端口找出并杀掉占用进程
 */
function killByPorts() {
  const result = [];
  for (const port of PORTS_TO_CHECK) {
    try {
      const cmd = `netstat -ano | findstr ":${port} " | findstr "LISTENING"`;
      const out = execSync(cmd, { encoding: 'utf8', timeout: 3000, stdio: 'pipe' });
      const lines = out.trim().split(/\r?\n/);
      const seen = new Set();
      for (const line of lines) {
        const m = line.trim().match(/(\d+)\s*$/);
        if (!m) continue;
        const pid = parseInt(m[1]);
        if (seen.has(pid)) continue;
        seen.add(pid);
        // 不要杀自己
        if (pid === process.pid) continue;
        if (windowsKill(pid)) result.push(`port ${port} (pid ${pid})`);
      }
    } catch {}
  }
  return result;
}

/**
 * 通过进程名找出与本项目相关的旧进程并杀掉
 */
function killByName() {
  const result = [];
  // desktopclaw 的 Python 后端进程（命令行中含 desktopclaw api/gateway）
  try {
    const cmd = `wmic process where "name='python.exe'" get ProcessId,CommandLine /format:csv`;
    const out = execSync(cmd, { encoding: 'utf8', timeout: 5000, stdio: 'pipe' });
    const lines = out.trim().split(/\r?\n/);
    for (let i = 1; i < lines.length; i++) { // 跳过 CSV 头
      const line = lines[i].trim();
      if (!line || !line.toLowerCase().includes('desktopclaw')) continue;
      const parts = line.split(',');
      const pidStr = parts[parts.length - 1];
      const pid = parseInt(pidStr);
      if (isNaN(pid) || pid === process.pid) continue;
      if (windowsKill(pid)) result.push(`desktopclaw python (pid ${pid})`);
    }
  } catch {}
  return result;
}

/**
 * Kill stale DesktopClaw Electron dev instances (same --dev flag, project path).
 * Avoids GPU cache lock conflicts when restart.bat without closing the pet.
 */
function killStaleElectron() {
  const result = [];
  const projectMarker = 'desktopclaw';
  try {
    const cmd = `wmic process where "name='electron.exe'" get ProcessId,CommandLine /format:csv`;
    const out = execSync(cmd, { encoding: 'utf8', timeout: 5000, stdio: 'pipe' });
    const lines = out.trim().split(/\r?\n/);
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i].trim();
      if (!line || !line.includes('--dev')) continue;
      if (!line.toLowerCase().includes(projectMarker)) continue;
      const parts = line.split(',');
      const pid = parseInt(parts[parts.length - 1]);
      if (isNaN(pid) || pid === process.pid) continue;
      if (windowsKill(pid)) result.push(`electron dev (pid ${pid})`);
    }
  } catch {}
  return result;
}

function killResidualProcesses() {
  console.log('[Cleanup] Checking for leftover processes from previous run...');

  const killedByPort = killByPorts();
  const killedByName = killByName();
  const killedElectron = killStaleElectron();

  // 去重
  const all = [...new Set([...killedByPort, ...killedByName, ...killedElectron])];

  if (all.length > 0) {
    console.log(`[Cleanup] Killed residual processes: ${all.join(', ')}`);
  } else {
    console.log('[Cleanup] No residual processes found');
  }
}

killResidualProcesses();

// ============================================================
// 依赖检测与自动安装
// ============================================================

const ROOT_DIR = path.resolve(__dirname, '..');
const BACKEND_DIR = path.join(ROOT_DIR, 'backend');
const PKG_JSON = path.join(__dirname, 'package.json');

function checkFrontendDeps() {
  if (!fs.existsSync(PKG_JSON)) {
    console.error('[DepCheck] package.json not found');
    return false;
  }
  const pkg = JSON.parse(fs.readFileSync(PKG_JSON, 'utf-8'));
  const allDeps = { ...pkg.dependencies, ...pkg.devDependencies };
  const nodeModulesDir = path.join(__dirname, 'node_modules');

  if (!fs.existsSync(nodeModulesDir)) {
    console.log('[DepCheck] node_modules missing');
    return false;
  }

  const missing = [];
  for (const dep of Object.keys(allDeps)) {
    const depPath = dep.startsWith('@')
      ? path.join(nodeModulesDir, dep)
      : path.join(nodeModulesDir, dep);
    if (!fs.existsSync(depPath)) missing.push(dep);
  }

  if (missing.length > 0) {
    console.log(`[DepCheck] Missing ${missing.length} frontend deps: ${missing.slice(0, 10).join(', ')}${missing.length > 10 ? '...' : ''}`);
    return false;
  }
  console.log('[DepCheck] Frontend deps OK');
  return true;
}

function installFrontendDeps() {
  return new Promise((resolve, reject) => {
    console.log('[DepCheck] Installing frontend deps (npm install)...');
    const proc = spawn('npm', ['install', '--no-audit', '--no-fund'], {
      cwd: __dirname, stdio: ['ignore', 'pipe', 'pipe'], shell: true
    });
    let output = '';
    proc.stdout.on('data', (d) => { output += d.toString(); });
    proc.stderr.on('data', (d) => { output += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0) { console.log('[DepCheck] Frontend deps installed'); resolve(); }
      else { console.error('[DepCheck] Frontend deps install FAILED'); console.error(output); reject(new Error('npm install failed')); }
    });
    proc.on('error', reject);
  });
}

function checkBackendDeps() {
  const expected = BACKEND_DIR.replace(/\\/g, '\\\\');
  const cmd = [
    'python -c "',
    'import pathlib, desktopclaw, sys;',
    `e=pathlib.Path(r'${expected}').resolve();`,
    'a=pathlib.Path(desktopclaw.__file__).resolve().parent.parent;',
    'sys.exit(0 if a==e else 1)',
    '"',
  ].join(' ');
  try {
    execSync(cmd, { cwd: BACKEND_DIR, stdio: 'pipe', timeout: 15000 });
    console.log('[DepCheck] Python backend deps OK (workspace)');
    return true;
  } catch {
    console.log('[DepCheck] Backend not linked to workspace — will reinstall');
    return false;
  }
}

function installBackendDeps() {
  return new Promise((resolve, reject) => {
    console.log('[DepCheck] Installing backend deps (pip install -e .)...');
    const proc = spawn('pip', ['install', '-e', '.'], {
      cwd: BACKEND_DIR, stdio: ['ignore', 'pipe', 'pipe'], shell: true
    });
    let output = '';
    proc.stdout.on('data', (d) => { output += d.toString(); });
    proc.stderr.on('data', (d) => { output += d.toString(); });
    proc.on('close', (code) => {
      if (code === 0) { console.log('[DepCheck] Backend deps installed'); resolve(); }
      else { console.error('[DepCheck] Backend deps install FAILED'); console.error(output); reject(new Error('pip install failed')); }
    });
    proc.on('error', reject);
  });
}

async function ensureDependencies() {
  console.log('========================================');
  console.log('  Dependency Check');
  console.log('========================================');

  if (!checkFrontendDeps()) {
    await installFrontendDeps();
    checkFrontendDeps();
  }

  if (!checkBackendDeps()) {
    await installBackendDeps();
    checkBackendDeps();
  }

  console.log('========================================');
  console.log('  Ready to launch');
  console.log('========================================\n');
}

// ============================================================
// 启动逻辑
// ============================================================

function checkPort(port) {
  return new Promise((resolve) => {
    const req = http.request({
      hostname: 'localhost', port, path: '/', method: 'GET', timeout: 2000
    }, () => resolve(true));
    req.on('error', () => resolve(false));
    req.on('timeout', () => { req.destroy(); resolve(false); });
    req.end();
  });
}

async function waitForVite(maxAttempts = 30) {
  for (let i = 0; i < maxAttempts; i++) {
    for (const port of [5173, 5174, 5175, 5176]) {
      if (await checkPort(port)) return port;
    }
    await new Promise(r => setTimeout(r, 1000));
  }
  throw new Error('Vite did not start within 30s');
}

async function main() {
  try {
    await ensureDependencies();
  } catch (err) {
    console.error('[DepCheck] Error:', err.message);
    console.log('[DepCheck] Continuing anyway...');
  }

  const vite = spawn('npm', ['run', 'dev'], {
    stdio: 'inherit', shell: true
  });

  waitForVite().then((port) => {
    console.log(`[Launch] Vite ready on :${port}, starting Electron...`);

    const electron = spawn('electron', ['.', '--dev'], {
      stdio: 'inherit',
      shell: true,
      env: { ...process.env, VITE_PORT: String(port) }
    });

    electron.on('close', (code) => {
      console.log(`[Launch] Electron exited (code ${code})`);
      vite.kill();
      process.exit(code);
    });
  }).catch((err) => {
    console.error('[Launch] Failed:', err);
    vite.kill();
    process.exit(1);
  });

  process.on('SIGINT', () => { vite.kill(); process.exit(0); });
}

main();
