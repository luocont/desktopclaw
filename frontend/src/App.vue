<template>
  <!--
    Bug #1: hover detection used to be on `.pet-container`, which sits at
    petWidth × petHeight only. The chat bubble is positioned `top: 100%`
    (i.e. *outside* that container), so moving the cursor onto the bubble
    fired `mouseleave` → click-through ON → bubble was unclickable.
    Hooking the listeners onto the wrapper makes any visible UI inside the
    Electron window count as "interactive".
  -->
  <div
    class="desktop-pet-wrapper"
    ref="wrapperEl"
    @mouseenter="onPetAreaEnter"
    @mouseleave="onPetAreaLeave"
  >
    <div
      class="pet-row"
      ref="petRow"
      :style="{ height: live2d.petHeight() + 'px' }"
    >
      <ModelPicker
        :visible="showModelPicker"
        @close="showModelPicker = false"
        @pick="onPickModel"
        @opened="onPanelOpened"
        ref="modelPickerRef"
      />

      <SettingsPanel
        :visible="showSettings"
        @close="showSettings = false"
        @opened="onPanelOpened"
        ref="settingsPanelRef"
      />

      <div
        class="pet-container"
        ref="petContainer"
        :style="petContainerStyle"
      >
        <ChatPanel
          :visible="showDialog"
          :expanded="isDialogExpanded"
          @close="showDialog = false"
          @toggleExpand="isDialogExpanded = !isDialogExpanded"
          @sized="onDialogSized"
          ref="chatPanelRef"
        />

        <Live2DStage @close="closePet" ref="live2dStageRef" />

        <ControlButtons
          :scale="live2d.petScale.value"
          :dialog="showDialog"
          :modelPicker="showModelPicker"
          :settings="showSettings"
          @toggle="onTogglePanel"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, watch } from 'vue'
import ChatPanel from './components/ChatPanel.vue'
import Live2DStage from './components/Live2DStage.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import ModelPicker from './components/ModelPicker.vue'
import ControlButtons from './components/ControlButtons.vue'
import { useLive2D } from './stores/useLive2D.js'
import { useSettings } from './stores/useSettings.js'
import { useReminder } from './stores/useReminder.js'
import { useFeishuSSE } from './composables/useFeishuSSE.js'
import { useClickThrough } from './composables/useClickThrough.js'
import { hasElectronApi, callElectronApi, getElectronApi } from './utils/electronBridge.js'

// ---- Top-level UI panel toggles -----------------------------------------
const showDialog = ref(false)
const isDialogExpanded = ref(false)
const showModelPicker = ref(false)
const showSettings = ref(false)

const petContainer = ref(null)
const petRow = ref(null)
const wrapperEl = ref(null)
const chatPanelRef = ref(null)
const live2dStageRef = ref(null)
const settingsPanelRef = ref(null)
const modelPickerRef = ref(null)

/** Screen X of the Live2D doll — kept constant when side panels open/close. */
let petAnchorScreenX = null

// ---- Stores --------------------------------------------------------------
const live2d = useLive2D()
const settings = useSettings()
const reminder = useReminder()
const feishu = useFeishuSSE()
const click = useClickThrough()

// ---- Pet container geometry --------------------------------------------
// Live2D stays at a fixed position inside pet-container; left panels sit
// in the flex row to its left. Window x is adjusted so the doll's screen
// coordinates never move when panels toggle.
const petContainerStyle = computed(() => ({
  width: live2d.petWidth() + 'px',
  height: live2d.petHeight() + 'px',
}))

/** Collect bounding boxes of chrome that can extend past the pet row. */
function collectOverflowRects() {
  const rects = []
  const add = (el) => {
    if (!el || el.nodeType !== 1) return
    const style = window.getComputedStyle(el)
    if (style.display === 'none' || style.visibility === 'hidden') return
    rects.push(el.getBoundingClientRect())
  }
  if (showDialog.value) add(chatPanelRef.value?.bubbleEl)
  add(petContainer.value?.querySelector('.interaction-bubble'))
  return rects
}

async function updateWindowSize() {
  if (!hasElectronApi('resizePetWindow')) return
  await nextTick()

  const pos = await callElectronApi('getWindowPosition')
  const pet = petContainer.value
  if (!pet) return

  const winX = pos?.x ?? 0
  const winY = pos?.y ?? 0

  const petRect = pet.getBoundingClientRect()
  // Anchor in screen space so the doll does not jump when side panels open.
  const petScreenLeft = winX + petRect.left

  if (!showSettings.value && !showModelPicker.value) {
    petAnchorScreenX = petScreenLeft
  } else if (petAnchorScreenX === null) {
    petAnchorScreenX = petScreenLeft
  }

  // Reposition window so the pet's screen X stays fixed while panels toggle.
  const newWinX = Math.round(petAnchorScreenX - petRect.left)
  const newWinY = winY

  // Size from viewport (client) coordinates only — never mix with screen coords.
  let contentLeft = 0
  let contentRight = petRect.right
  let contentBottom = petRect.bottom

  const row = petRow.value
  if (row) {
    const r = row.getBoundingClientRect()
    contentLeft = Math.min(contentLeft, r.left)
    contentRight = Math.max(contentRight, r.right)
    contentBottom = Math.max(contentBottom, r.bottom)
  }
  const btnRow = pet.querySelector('.button-row')
  if (btnRow) {
    const br = btnRow.getBoundingClientRect()
    contentLeft = Math.min(contentLeft, br.left)
    contentRight = Math.max(contentRight, br.right)
    contentBottom = Math.max(contentBottom, br.bottom)
  }
  for (const r of collectOverflowRects()) {
    contentLeft = Math.min(contentLeft, r.left)
    contentRight = Math.max(contentRight, r.right)
    contentBottom = Math.max(contentBottom, r.bottom)
  }

  const width = Math.max(Math.ceil(contentRight - contentLeft), live2d.petWidth() + 60)
  const height = Math.max(Math.ceil(contentBottom), live2d.petHeight())

  callElectronApi('resizePetWindow', newWinX, newWinY, width, height)
  live2d.applyResize()
}

function onPanelOpened() {
  setTimeout(updateWindowSize, 0)
}

watch(
  [showDialog, isDialogExpanded, showModelPicker, showSettings, () => live2d.petScale.value],
  async () => {
    await nextTick()
    setTimeout(updateWindowSize, 50)
  },
)

watch(
  () => live2d.isModelLoaded.value,
  (loaded) => {
    if (loaded) setTimeout(updateWindowSize, 50)
  },
)

function onDialogSized() {
  setTimeout(updateWindowSize, 50)
}

// ---- Click-through (transparent area passes mouse events to OS) --------
function onPetAreaEnter() { click.set(false) }
function onPetAreaLeave() { click.set(true) }

// ---- Panel exclusivity --------------------------------------------------
function onTogglePanel(which) {
  showDialog.value      = which === 'dialog'      ? !showDialog.value      : false
  showModelPicker.value = which === 'modelPicker' ? !showModelPicker.value : false
  showSettings.value    = which === 'settings'    ? !showSettings.value    : false
}

async function onPickModel(path) {
  // Bug #16: previously this dug the canvas out via
  // document.getElementById('live2d-canvas'). The store now reuses the
  // existing PIXI view internally, so we don't need to break the
  // component boundary.
  await live2d.switchModel(path)
}

function closePet() {
  live2d.cleanup()
  if (hasElectronApi('closeWindow')) {
    callElectronApi('closeWindow')
  } else {
    const wrapper = document.querySelector('.desktop-pet-wrapper')
    if (wrapper) wrapper.style.display = 'none'
  }
}

// ---- Lifecycle ----------------------------------------------------------
onMounted(async () => {
  click.set(true)

  settings.loadFromBackend()
  await live2d.scanModels()

  // Wait for Live2D canvas init before fitting the Electron window.
  await nextTick()
  setTimeout(updateWindowSize, 600)

  feishu.start()
  setTimeout(() => reminder.start(), 1000)

  // Multi-screen info — Electron pushes updates when monitors come/go.
  if (hasElectronApi('onScreenInfoUpdated')) {
    getElectronApi().onScreenInfoUpdated((info) => {
      console.log('[App] Screen info updated:', JSON.stringify(info))
    })
  }
})

onUnmounted(() => {
  feishu.stop()
  reminder.clearAll()
  if (hasElectronApi('removeScreenInfoListener')) {
    callElectronApi('removeScreenInfoListener')
  }
})
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.desktop-pet-wrapper {
  width: 100%;
  height: 100%;
  background: transparent;
  overflow: visible;
  position: relative;
}

.pet-row {
  display: flex;
  flex-direction: row;
  align-items: flex-start;
}

.pet-container {
  position: relative;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: var(--space-sm);
  z-index: var(--z-modal);
  user-select: none;
  -webkit-user-select: none;
}

/* ===== 对话框气泡 - Glassmorphism + Indigo ===== */
.dialog-bubble {
  position: absolute;
  left: 0;
  top: 100%;
  margin-top: 8px;
  width: 340px;
  max-height: 420px;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  z-index: 1000;
  transition: width 0.3s ease, height 0.3s ease;
}

.dialog-bubble.expanded {
  /* Bug #4: 50vh / 50vw bound the bubble to a viewport that itself was
     being resized by updateWindowSize, producing either oscillation or
     clipping. Fixed pixels make both ends of the loop deterministic. */
  width: 480px;
  height: 480px;
  max-height: 480px;
}

.dialog-bubble.dragging {
  transition: none;
  cursor: move;
}

.bubble-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-lg);
  background: var(--accent-indigo);
  border-bottom: 1px solid var(--glass-border);
  cursor: move;
  user-select: none;
}

.bubble-header-btns {
  display: flex;
  gap: var(--space-sm);
  align-items: center;
}

.bubble-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.5px;
}

.bubble-expand-btn,
.bubble-close {
  background: rgba(255, 255, 255, 0.15);
  border: none;
  color: var(--text-primary);
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast);
}

.bubble-expand-btn:hover,
.bubble-close:hover {
  background: rgba(255, 255, 255, 0.25);
}

.bubble-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md);
  max-height: 280px;
  min-height: 60px;
  scroll-behavior: smooth;
  background: var(--bg-secondary);
}

.dialog-bubble.expanded .bubble-messages { max-height: none; }

.bubble-messages::-webkit-scrollbar { width: 4px; }
.bubble-messages::-webkit-scrollbar-track { background: transparent; }
.bubble-messages::-webkit-scrollbar-thumb { background: var(--glass-border); border-radius: var(--radius-sm); }

.bubble-message {
  margin-bottom: var(--space-sm);
  max-width: 88%;
  animation: msgSlideIn 0.25s ease-out;
}

@keyframes msgSlideIn {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0);   }
}

.bubble-user { margin-left: auto; }
.bubble-ai   { margin-right: auto; }

.bubble-message-content {
  display: inline-block;
  padding: 10px var(--space-md);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  line-height: 1.5;
  word-wrap: break-word;
  text-align: left;
}

.bubble-user .bubble-message-content {
  background: var(--accent-indigo);
  color: var(--text-primary);
  border-bottom-right-radius: var(--radius-sm);
}

.bubble-ai .bubble-message-content {
  background: var(--glass-bg-strong);
  color: var(--text-secondary);
  border: 1px solid var(--glass-border);
  border-bottom-left-radius: var(--radius-sm);
}

.tool-call-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  color: var(--text-muted);
}

.tool-icon { color: var(--text-muted); }

.tool-text {
  font-family: monospace;
  background: var(--glass-bg-strong);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
}

.thinking-indicator { display: flex; align-items: center; gap: 6px; }

.thinking-dots {
  font-style: italic;
  color: var(--text-muted);
  font-size: var(--font-size-sm);
}

.audio-message,
.tts-message {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.audio-icon, .tts-icon { color: var(--text-muted); }

.audio-player { max-width: 160px; height: 28px; }

.bubble-input {
  display: flex;
  gap: var(--space-sm);
  padding: var(--space-md);
  border-top: 1px solid var(--glass-border);
  background: var(--glass-bg);
}

.bubble-input-field {
  flex: 1;
  padding: 8px var(--space-md);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-full);
  font-size: var(--font-size-base);
  outline: none;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  transition: border-color var(--transition-fast);
}

.bubble-input-field::placeholder { color: var(--text-subtle); }
.bubble-input-field:focus { border-color: var(--accent-indigo-light); }
.bubble-input-field:disabled {
  background: var(--bg-secondary);
  cursor: not-allowed;
  opacity: 0.6;
}

.bubble-send-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  border: none;
  background: var(--accent-indigo);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  flex-shrink: 0;
  color: var(--text-primary);
}

.bubble-send-btn:hover:not(:disabled) {
  background: var(--accent-indigo-light);
  transform: scale(1.05);
}
.bubble-send-btn:active:not(:disabled) { transform: scale(0.95); }
.bubble-send-btn:disabled { opacity: 0.4; cursor: not-allowed; }

.loading-dots { color: var(--text-primary); font-size: var(--font-size-base); }

.bubble-record-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  border: 1px solid var(--glass-border);
  background: var(--glass-bg-strong);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast);
  flex-shrink: 0;
  color: var(--text-secondary);
}
.bubble-record-btn:hover:not(:disabled) { background: var(--glass-bg); }
.bubble-record-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.bubble-record-btn.recording {
  background: var(--error);
  color: var(--text-primary);
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
}

.bubble-arrow {
  position: absolute;
  left: 30px;
  top: -8px;
  width: 0;
  height: 0;
  border-left: 8px solid transparent;
  border-right: 8px solid transparent;
  border-bottom: 8px solid var(--glass-bg);
}

.bubble-fade-enter-active { animation: bubbleIn 0.3s ease-out; }
.bubble-fade-leave-active { animation: bubbleOut 0.2s ease-in; }

/* Bug #21: previous keyframes used translateY(-50%) which made the bubble
   visually jump to the top half of the pet during the animation, even
   though its resting position is `top: 100%` (below the pet). Drop the Y
   translation — slide-in from the left + fade is sufficient and matches
   the bubble's actual landing spot. */
@keyframes bubbleIn {
  from { opacity: 0; transform: translateX(-10px) scale(0.95); }
  to   { opacity: 1; transform: translateX(0)     scale(1);    }
}
@keyframes bubbleOut {
  from { opacity: 1; transform: translateX(0)     scale(1);    }
  to   { opacity: 0; transform: translateX(-10px) scale(0.95); }
}

/* ===== Live2D ===== */
.live2d-wrapper {
  width: 300px;
  height: 400px;
  cursor: grab;
  position: relative;
}

.live2d-wrapper:active { cursor: grabbing; }

.resize-handle {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: nwse-resize;
  opacity: 0.7;
  transition: opacity 0.2s ease;
  color: #fff;
  background: rgba(0, 0, 0, 0.5);
  border: 2px solid #fff;
  border-radius: 4px;
  z-index: 10;
}
.resize-handle:hover { opacity: 1; background: rgba(0, 0, 0, 0.7); }

.close-btn {
  position: absolute;
  top: 4px;
  right: 28px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  opacity: 0.7;
  transition: opacity 0.2s ease;
  color: #fff;
  background: rgba(255, 0, 0, 0.6);
  border: 2px solid #fff;
  border-radius: 4px;
  z-index: 10;
  padding: 0;
}
.close-btn:hover { opacity: 1; background: rgba(255, 0, 0, 0.8); }

#live2d-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.interaction-bubble {
  /* Bug #12: positioned to the LEFT of live2d-wrapper used to push the
     bubble outside the Electron window's left edge (window starts at
     pet-container's left:0 and the bubble extended to negative X). Move
     it to the top-right corner of the model instead, where the Electron
     window already has slack from the ControlButtons row. */
  position: absolute;
  left: calc(100% + 8px);
  top: 0;
  padding: 10px 14px;
  max-width: 200px;
  border-radius: var(--radius-lg);
  background: rgba(30, 30, 50, 0.95);
  border: 1px solid rgba(255, 255, 255, 0.2);
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
  z-index: 10;
}

.interaction-message {
  font-size: var(--font-size-sm);
  color: #ffffff;
  line-height: 1.6;
  text-align: left;
  width: 110px;
  word-break: break-all;
  white-space: pre-wrap;
}

.interaction-arrow {
  /* Pointing FROM the bubble TOWARDS the model (model is on the left now). */
  position: absolute;
  right: 100%;
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-right: 8px solid var(--glass-bg-strong);
}

.interaction-fade-enter-active { animation: interactionIn 0.3s ease-out; }
.interaction-fade-leave-active { animation: interactionOut 0.2s ease-in; }

@keyframes interactionIn {
  from { opacity: 0; transform: translateX(-10px); }
  to   { opacity: 1; transform: translateX(0);     }
}
@keyframes interactionOut {
  from { opacity: 1; transform: translateX(0);     }
  to   { opacity: 0; transform: translateX(-10px); }
}

.live2d-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 20;
  color: var(--text-secondary);
  font-size: var(--font-size-base);
  background: var(--glass-bg-strong);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-full);
  border: 1px solid var(--glass-border);
}

/* ===== 按钮行 ===== */
.button-row {
  position: absolute;
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-left: 10px;
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.toggle-dialog-btn,
.model-switch-btn,
.settings-btn {
  /* Bug #11: settings-btn used to be white-on-transparent while the
     other two were dark-on-grey, making the row look half-finished. Use
     one consistent base style; per-button accent colours apply only on
     the .active state below. */
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  background: #1a1a1a;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-normal);
  z-index: calc(var(--z-modal) + 2);
  color: var(--text-secondary);
  border: 1px solid #333;
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.15);
}

.toggle-dialog-btn:hover,
.model-switch-btn:hover,
.settings-btn:hover {
  transform: scale(1.1);
  background: #2a2a2a;
  color: var(--text-primary);
}

.toggle-dialog-btn.active {
  background: var(--accent-indigo);
  color: var(--text-primary);
}

.model-switch-btn.active {
  background: var(--accent-amber);
  color: var(--text-primary);
}

.settings-btn.active {
  background: var(--accent-amber);
  color: var(--text-primary);
}

/* ===== Markdown 样式 ===== */
.markdown-body {
  font-size: var(--font-size-base);
  line-height: 1.6;
  word-wrap: break-word;
  overflow-wrap: break-word;
  color: var(--text-secondary);
}

.markdown-body p { margin: 0 0 var(--space-sm) 0; }
.markdown-body p:last-child { margin-bottom: 0; }

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  margin: var(--space-md) 0 var(--space-sm) 0;
  font-weight: 600;
  line-height: 1.3;
  color: var(--text-primary);
}

.markdown-body h1 { font-size: var(--font-size-lg); }
.markdown-body h2 { font-size: var(--font-size-md); }
.markdown-body h3 { font-size: var(--font-size-base); }

.markdown-body ul,
.markdown-body ol {
  margin: var(--space-sm) 0;
  padding-left: 20px;
}
.markdown-body li { margin: 2px 0; }

.markdown-body code {
  background: var(--glass-bg-strong);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: var(--font-size-sm);
  color: var(--accent-indigo-light);
}

.markdown-body pre {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  margin: var(--space-sm) 0;
  overflow-x: auto;
  font-size: var(--font-size-sm);
  line-height: 1.5;
  border: 1px solid var(--glass-border);
}
.markdown-body pre code { background: none; padding: 0; color: inherit; font-size: inherit; }

.markdown-body blockquote {
  border-left: 3px solid var(--accent-indigo);
  padding: var(--space-sm) var(--space-md);
  margin: var(--space-sm) 0;
  color: var(--text-muted);
  background: var(--glass-bg);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: var(--space-sm) 0;
  font-size: var(--font-size-sm);
}
.markdown-body th,
.markdown-body td {
  border: 1px solid var(--glass-border);
  padding: var(--space-sm);
  text-align: left;
}
.markdown-body th {
  background: var(--glass-bg-strong);
  font-weight: 600;
  color: var(--text-primary);
}

.markdown-body a { color: var(--accent-indigo-light); text-decoration: none; }
.markdown-body a:hover { text-decoration: underline; }

.markdown-body hr {
  border: none;
  border-top: 1px solid var(--glass-border);
  margin: var(--space-md) 0;
}

.markdown-body img {
  max-width: 100%;
  border-radius: var(--radius-sm);
  margin: var(--space-sm) 0;
}

.markdown-body strong { font-weight: 600; color: var(--text-primary); }

/* ===== 皮肤选择器 - Glassmorphism + Amber ===== */
.model-picker {
  flex-shrink: 0;
  width: 220px;
  height: 100%;
  margin-right: 20px;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-lg);
  overflow: hidden;
  z-index: calc(var(--z-modal) + 1);
}

.picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-lg);
  background: var(--accent-amber);
  border-bottom: 1px solid var(--glass-border);
}

.picker-header span {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--text-primary);
}

.picker-close {
  background: rgba(255, 255, 255, 0.15);
  border: none;
  color: var(--text-primary);
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast);
}
.picker-close:hover { background: rgba(255, 255, 255, 0.25); }

.picker-list {
  padding: var(--space-sm);
  flex: 1;
  min-height: 0;
  max-height: none;
  overflow-y: auto;
  background: var(--bg-secondary);
}
.picker-list::-webkit-scrollbar { width: 4px; }
.picker-list::-webkit-scrollbar-track { background: transparent; }
.picker-list::-webkit-scrollbar-thumb { background: var(--glass-border); border-radius: var(--radius-sm); }

.picker-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 10px var(--space-md);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-bottom: 2px;
}
.picker-item:last-child { margin-bottom: 0; }
.picker-item:hover { background: var(--glass-bg-strong); }
.picker-item.active {
  background: rgba(217, 119, 6, 0.15);
  border: 1px solid rgba(217, 119, 6, 0.3);
}
.picker-item-icon { flex-shrink: 0; color: var(--text-muted); }
.picker-item.active .picker-item-icon { color: var(--accent-amber); }
.picker-item-name {
  flex: 1;
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  font-weight: 500;
}
.picker-item.active .picker-item-name { color: var(--accent-amber); font-weight: 600; }
.picker-check { color: var(--accent-amber); flex-shrink: 0; }

.picker-empty {
  text-align: center;
  padding: var(--space-xl) var(--space-md);
  color: var(--text-muted);
  font-size: var(--font-size-base);
}

.settings-panel {
  flex-shrink: 0;
  width: 280px;
  height: 100%;
  margin-right: 20px;
  display: flex;
  flex-direction: column;
  border-radius: var(--radius-lg);
  overflow: hidden;
  z-index: 1001;
}

.settings-form {
  padding: var(--space-md);
  display: flex;
  flex-direction: column;
  gap: var(--space-md);
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  background: var(--bg-secondary);
}

.settings-field { display: flex; flex-direction: column; gap: 6px; }

.settings-label {
  font-size: var(--font-size-sm);
  font-weight: 600;
  color: var(--text-secondary);
}

.settings-input,
.settings-textarea {
  padding: 8px 12px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  background: var(--glass-bg);
  color: var(--text-primary);
  font-size: var(--font-size-sm);
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s ease;
}
.settings-textarea { resize: vertical; }
.settings-input:focus,
.settings-textarea:focus { border-color: var(--accent-amber); }

.settings-save-btn {
  padding: 8px 16px;
  background: var(--accent-amber);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-size-sm);
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s ease;
}
.settings-save-btn:hover { opacity: 0.85; }
.settings-save-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.personality-options { display: flex; gap: var(--space-sm); }

.personality-btn {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-md);
  background: var(--glass-bg);
  color: var(--text-secondary);
  font-size: var(--font-size-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition-fast);
}
.personality-btn:hover { background: var(--glass-bg-strong); border-color: var(--accent-amber); }
.personality-btn.active {
  background: var(--accent-amber);
  color: white;
  border-color: var(--accent-amber);
}

.settings-btn:hover { background: #2a2a2a; color: var(--text-primary); }

.picker-fade-enter-active { animation: pickerIn 0.25s ease-out; }
.picker-fade-leave-active { animation: pickerOut 0.15s ease-in; }

@keyframes pickerIn {
  from { opacity: 0; transform: translateX(-10px) scale(0.95); }
  to   { opacity: 1; transform: translateX(0) scale(1); }
}
@keyframes pickerOut {
  from { opacity: 1; transform: translateX(0) scale(1); }
  to   { opacity: 0; transform: translateX(-10px) scale(0.95); }
}
</style>
