import { createApp } from 'vue'
import './globals.css'
import './shared-components.css'

function getAppMode() {
  const params = new URLSearchParams(window.location.search)
  const mode = params.get('mode')
  if (mode === 'launcher' || mode === 'chat') return mode
  return 'pet'
}

function applyOpaqueBackground() {
  document.documentElement.setAttribute('data-ui', 'opaque')
  document.body.style.background = '#FAFAFA'
  const appEl = document.getElementById('app')
  if (appEl) appEl.style.background = '#FAFAFA'
}

async function bootstrap() {
  const mode = getAppMode()

  if (mode === 'launcher' || mode === 'chat') {
    applyOpaqueBackground()
  }

  const loaders = {
    launcher: () => import('./UiLauncher.vue'),
    pet: () => import('./App.vue'),
    chat: () => import('./ChatApp.vue'),
  }

  const { default: Root } = await loaders[mode]()
  createApp(Root).mount('#app')
}

bootstrap()
