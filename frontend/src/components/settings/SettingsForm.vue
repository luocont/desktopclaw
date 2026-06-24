<template>
  <div class="settings-form">
    <p class="settings-page-hint">
      修改即时生效；保存按钮用于持久化到本地和后端。
    </p>
    <div class="settings-page-field">
      <label class="settings-page-label">API Base URL（LLM接口地址）</label>
      <input
        v-model="settings.baseUrl.value"
        type="text"
        class="settings-page-input"
        placeholder="留空使用默认值"
      />
    </div>
    <div class="settings-page-field">
      <label class="settings-page-label">API Key</label>
      <input
        v-model="settings.apiKey.value"
        type="password"
        class="settings-page-input"
        placeholder="sk-..."
      />
    </div>
    <div class="settings-page-field">
      <label class="settings-page-label">主模型</label>
      <input
        v-model="settings.modelId.value"
        type="text"
        class="settings-page-input"
        placeholder="deepseek-chat"
      />
    </div>
    <div class="settings-page-field">
      <label class="settings-page-label">快速模型</label>
      <input
        v-model="settings.fastModelId.value"
        type="text"
        class="settings-page-input"
        placeholder="gpt-4o-mini"
      />
      <p class="settings-page-hint">用于深度调研单页摘要，留空则使用主模型</p>
    </div>
    <div class="settings-page-field">
      <label class="settings-page-label">角色性格</label>
      <div class="settings-page-personality">
        <button
          v-for="opt in personalityOptions"
          :key="opt.value"
          type="button"
          :class="['settings-page-personality-btn', { active: settings.personality.value === opt.value }]"
          @click="settings.personality.value = opt.value"
          :title="opt.description"
        >
          {{ opt.label }}
        </button>
      </div>
    </div>
    <div class="settings-page-field">
      <label class="settings-page-label">生日</label>
      <input v-model="settings.birthday.value" type="date" class="settings-page-input" />
    </div>
    <div class="settings-page-field">
      <label class="settings-page-label">自定义提示词</label>
      <textarea
        v-model="settings.customPrompt.value"
        class="settings-page-textarea"
        placeholder="留空则使用默认提示词"
        rows="4"
      />
    </div>
    <div v-if="showSwitchToChat" class="settings-page-actions">
      <button type="button" class="settings-page-secondary-btn" @click="onSwitchToChat">
        切换到聊天窗口
      </button>
    </div>
    <div v-if="showMemoryButton" class="settings-page-actions">
      <button type="button" class="settings-page-secondary-btn" @click="$emit('openMemory')">
        打开记忆库
      </button>
    </div>
    <div class="settings-page-actions">
      <button
        type="button"
        class="settings-page-save-btn"
        @click="onSave"
        :disabled="settings.isSyncing.value"
      >
        {{ settings.isSyncing.value ? '保存中...' : '保存设置' }}
      </button>
    </div>
    <div v-if="saveStatus" class="settings-page-status" :class="{ error: saveError }">
      {{ saveStatus }}
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useSettings } from '../../stores/useSettings.js'
import { useChat } from '../../stores/useChat.js'
import { useConversations } from '../../stores/useConversations.js'
import { personalityOptions } from '../../data/personalities.js'
import { callElectronApi } from '../../utils/electronBridge.js'

defineProps({
  showMemoryButton: { type: Boolean, default: true },
  showSwitchToChat: { type: Boolean, default: false },
})

const emit = defineEmits(['openMemory', 'switchToChat'])

const settings = useSettings()
const chat = useChat()
const conversations = useConversations()
const saveStatus = ref('')
const saveError = ref(false)

async function onSave() {
  saveStatus.value = ''
  saveError.value = false
  const ok = await settings.save()
  if (ok) {
    saveStatus.value = '已保存（前后端同步）'
  } else {
    saveError.value = true
    const detail = settings.lastSyncError.value
    saveStatus.value = detail
      ? `同步失败：${detail}`
      : '已写入本地，但同步到后端失败（请确认 desktopclaw api 已启动）'
  }
}

function onSwitchToChat() {
  conversations.saveCurrent(chat.messages.value)
  conversations.syncSnapshot()
  emit('switchToChat')
  callElectronApi('switchUiMode', 'chat')
}
</script>
