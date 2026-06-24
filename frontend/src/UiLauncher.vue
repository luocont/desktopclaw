<template>
  <div class="launcher">
    <header class="launcher-header">
      <h1 class="launcher-title">DesktopClaw</h1>
      <p class="launcher-subtitle">选择界面模式</p>
    </header>

    <div class="launcher-choices">
      <button type="button" class="choice-card" @click="select('pet')">
        <div class="choice-preview pet-preview">
          <span class="preview-icon">🐾</span>
        </div>
        <div class="choice-text">
          <strong>桌面宠物</strong>
          <span>Live2D 悬浮助手，原 UI</span>
        </div>
      </button>

      <button type="button" class="choice-card" @click="select('chat')">
        <div class="choice-preview chat-preview">
          <span class="preview-icon">💬</span>
        </div>
        <div class="choice-text">
          <strong>聊天窗口</strong>
          <span>豆包式全屏对话，新 UI</span>
        </div>
      </button>
    </div>

    <label class="launcher-remember">
      <input v-model="remember" type="checkbox" />
      <span>记住选择，下次不再询问</span>
    </label>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { callElectronApi } from './utils/electronBridge.js'

const remember = ref(false)

function select(mode) {
  callElectronApi('launchUi', mode, remember.value)
}
</script>

<style scoped>
.launcher {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 24px;
  background: #FAFAFA;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.launcher-header {
  text-align: center;
  margin-bottom: 28px;
}

.launcher-title {
  font-size: 24px;
  font-weight: 700;
  color: #1A1A1A;
  margin: 0 0 6px;
}

.launcher-subtitle {
  font-size: 14px;
  color: #666;
  margin: 0;
}

.launcher-choices {
  display: flex;
  gap: 16px;
  width: 100%;
  max-width: 440px;
}

.choice-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  padding: 20px 16px;
  background: #FFFFFF;
  border: 1px solid #E8E8E8;
  border-radius: 16px;
  cursor: pointer;
  transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease;
  text-align: center;
}

.choice-card:hover {
  border-color: #D0D0D0;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
  transform: translateY(-2px);
}

.choice-preview {
  width: 64px;
  height: 64px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.pet-preview {
  background: linear-gradient(135deg, #4F46E5 0%, #6366F1 100%);
}

.chat-preview {
  background: linear-gradient(135deg, #F5F5F5 0%, #FFFFFF 100%);
  border: 1px solid #E8E8E8;
}

.preview-icon {
  font-size: 28px;
}

.choice-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.choice-text strong {
  font-size: 15px;
  color: #1A1A1A;
}

.choice-text span {
  font-size: 12px;
  color: #888;
  line-height: 1.4;
}

.launcher-remember {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 24px;
  font-size: 13px;
  color: #666;
  cursor: pointer;
  user-select: none;
}

.launcher-remember input {
  width: 16px;
  height: 16px;
  accent-color: #1A1A1A;
}
</style>
