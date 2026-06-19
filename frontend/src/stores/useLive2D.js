/**
 * Live2D store — owns the PIXI Application + the active Cubism4 model so a
 * single canvas can be shared across mounts/remounts and the model picker.
 *
 * The store keeps non-reactive references for `app` / `model` (pixi
 * objects don't survive Vue's reactive proxy cleanly) and exposes only
 * scalar reactive state to consumers.
 */

import { ref } from 'vue'
import * as PIXI from 'pixi.js'
import { Live2DModel } from 'pixi-live2d-display/cubism4'
import { fallbackModels, DEFAULT_MODEL_PATH } from '../data/models.js'
import { BASE_WIDTH, BASE_HEIGHT } from '../utils/constants.js'
import { hasElectronApi, getElectronApi } from '../utils/electronBridge.js'

const currentModelUrl = ref(DEFAULT_MODEL_PATH)
const availableModels = ref([])
const isModelLoaded = ref(false)
const modelError = ref('')
const petScale = ref(1)

// Non-reactive PIXI handles.
let app = null
let model = null
let idleTimer = null

function waitForCubismCore() {
  return new Promise((resolve, reject) => {
    let attempts = 0
    const id = setInterval(() => {
      attempts += 1
      if (typeof window !== 'undefined' && typeof window.Live2DCubismCore !== 'undefined') {
        clearInterval(id)
        resolve()
      } else if (attempts >= 50) {
        clearInterval(id)
        reject(new Error('Live2D Cubism Core 加载超时'))
      }
    }, 100)
  })
}

function ensurePixi(canvas) {
  if (app) return
  if (!canvas) throw new Error('Canvas 元素不存在')
  app = new PIXI.Application({
    view: canvas,
    width: Math.round(BASE_WIDTH * petScale.value),
    height: Math.round(BASE_HEIGHT * petScale.value),
    transparent: true,
    backgroundColor: 0x000000,
    backgroundAlpha: 0,
    clearBeforeRender: true,
    preserveDrawingBuffer: false,
    antialias: true,
    resolution: window.devicePixelRatio || 1,
    autoDensity: true,
  })
}

function petWidth()  { return Math.round(BASE_WIDTH  * petScale.value) }
function petHeight() { return Math.round(BASE_HEIGHT * petScale.value) }

function updateModelScale() {
  if (!model) return
  const targetHeight = petHeight() * 0.9
  const original = model.height / model.scale.y
  const s = targetHeight / original
  model.scale.set(s)
  model.x = (petWidth() - model.width) / 2
  model.y = (petHeight() - model.height) / 2
}

function applyResize() {
  if (!app) return
  app.renderer.resize(petWidth(), petHeight())
  updateModelScale()
}

function setupWatermarkRemoval() {
  if (!model || !currentModelUrl.value.includes('林翩翩')) return
  try { model.expression?.('水印') } catch (e) { console.warn('水印 expression 失败:', e) }
}

function playStartupAnimation() {
  if (!model) return
  try {
    const groups = model.internalModel.motionManager.motionGroups
    const expMgr = model.internalModel.motionManager.expressionManager
    const expNames = expMgr ? Object.keys(expMgr.expressions || {}) : []
    const firstGroup = Object.keys(groups)[0]
    if (firstGroup && model.motion) model.motion(firstGroup, 0, 3)
    if (expNames.length > 0 && model.expression) {
      const random = expNames[Math.floor(Math.random() * expNames.length)]
      setTimeout(() => model?.expression?.(random), 500)
      setTimeout(() => model?.expression?.(expNames[0]), 2000)
    }
  } catch (e) { console.warn('启动动画失败:', e) }
}

function startIdleAnimation() {
  if (!model) return
  const groups = model.internalModel.motionManager.motionGroups
  const expMgr = model.internalModel.motionManager.expressionManager
  const expNames = expMgr ? Object.keys(expMgr.expressions || {}) : []
  const groupNames = Object.keys(groups)

  const tick = () => {
    if (!model) return
    try {
      if (groupNames.length && model.motion) {
        const g = groupNames[Math.floor(Math.random() * groupNames.length)]
        const idx = Math.floor(Math.random() * (groups[g]?.length || 1))
        model.motion(g, idx, 1)
      }
      if (expNames.length && model.expression) {
        const e = expNames[Math.floor(Math.random() * expNames.length)]
        setTimeout(() => model?.expression?.(e), 500)
      }
    } catch (e) { console.warn('待机动作失败:', e) }
  }

  tick()
  idleTimer = setInterval(() => {
    if (model) tick()
    else clearInterval(idleTimer)
  }, 10000)
}

function setupModelInteraction() {
  if (!model) return
  model.eventMode = 'static'
  model.cursor = 'pointer'
  model.on('pointerdown', () => playRandomMotion())
}

function playRandomMotion() {
  if (!model) return
  try {
    const groups = model.internalModel.motionManager.motionGroups
    const expMgr = model.internalModel.motionManager.expressionManager
    const expNames = expMgr ? Object.keys(expMgr.expressions || {}) : []
    const groupNames = Object.keys(groups)
    if (groupNames.length && model.motion) {
      const g = groupNames[Math.floor(Math.random() * groupNames.length)]
      const idx = Math.floor(Math.random() * (groups[g]?.length || 1))
      model.motion(g, idx, 3)
      if (expNames.length && model.expression) {
        const r = expNames[Math.floor(Math.random() * expNames.length)]
        setTimeout(() => model?.expression?.(r), 300)
        setTimeout(() => model?.expression?.(expNames[0]), 2500)
      }
    }
  } catch (e) { console.warn('交互动画失败:', e) }
}

async function loadModel(canvas) {
  try {
    modelError.value = ''
    await waitForCubismCore()
    ensurePixi(canvas)
    if (typeof window !== 'undefined') window.PIXI = PIXI
    model = await Live2DModel.from(currentModelUrl.value)
    updateModelScale()
    app.stage.addChild(model)
    isModelLoaded.value = true
    setupWatermarkRemoval()
    playStartupAnimation()
    startIdleAnimation()
    setupModelInteraction()
  } catch (err) {
    console.error('Live2D 初始化失败:', err)
    modelError.value = err?.message || '模型加载失败'
    isModelLoaded.value = false
  }
}

function cleanupModel() {
  if (idleTimer) { clearInterval(idleTimer); idleTimer = null }
  if (model) {
    if (app?.stage) app.stage.removeChild(model)
    model.destroy()
    model = null
  }
  isModelLoaded.value = false
  modelError.value = ''
}

function cleanup() {
  cleanupModel()
  if (app) {
    app.destroy(true, { children: true, texture: true, baseTexture: true })
    app = null
  }
}

async function switchModel(path, canvas) {
  // Bug #16: callers used to fish the canvas out via
  // document.getElementById('live2d-canvas') because switchModel demanded
  // it. The PIXI app keeps a `view` reference once initialized, so
  // subsequent switches don't need to round-trip through the DOM at all.
  currentModelUrl.value = path
  cleanupModel()
  const reuseCanvas = canvas || app?.view || null
  await loadModel(reuseCanvas)
}

async function scanModels() {
  if (hasElectronApi('scanLive2DModels')) {
    try {
      const result = await getElectronApi().scanLive2DModels()
      if (result?.success && result.models?.length) {
        availableModels.value = result.models
        return
      }
    } catch (err) {
      console.error('扫描模型失败:', err)
    }
  }
  availableModels.value = fallbackModels
}

export function useLive2D() {
  return {
    // State
    currentModelUrl,
    availableModels,
    isModelLoaded,
    modelError,
    petScale,
    // Actions
    loadModel,
    switchModel,
    scanModels,
    applyResize,
    cleanup,
    // Geometry helpers
    petWidth,
    petHeight,
  }
}
