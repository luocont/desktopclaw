/**
 * Fallback Live2D model list used when the Electron model scanner is
 * unavailable (web/dev mode without the IPC bridge). Models actually
 * available depend on what's checked into `frontend/public/`.
 */

export const fallbackModels = [
  { name: 'Haru', path: '/Haru/Haru.model3.json' },
  { name: 'Mahiro', path: '/Mahiro_GG/Mahiro_V1.model3.json' },
  { name: 'UG', path: '/UG/ugofficial.model3.json' },
  { name: '弈', path: '/弈/13.model3.json' },
]

export const DEFAULT_MODEL_PATH = '/Haru/Haru.model3.json'
