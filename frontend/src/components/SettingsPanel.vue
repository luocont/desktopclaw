<template>
  <transition name="picker-fade" @after-enter="onOpened">
    <div v-if="visible" ref="panelEl" class="settings-panel glass-card" @click.stop>
      <div class="picker-header">
        <span>设置</span>
        <button class="picker-close" @click="$emit('close')" aria-label="关闭设置">
          <X :size="14" />
        </button>
      </div>
      <div class="settings-form">
        <!-- Bug #6: previously users were confused because edits took
             effect immediately (chatOptions is a computed ref) while the
             "保存" button only persisted to disk. Spell that out. -->
        <p class="settings-hint">
          修改即时生效；保存按钮用于持久化到本地和后端。
        </p>
        <div class="settings-field">
          <label class="settings-label">API Base URL（LLM接口地址）</label>
          <input
            v-model="settings.baseUrl.value"
            type="text"
            class="settings-input"
            placeholder="留空使用默认值"
          />
        </div>
        <div class="settings-field">
          <label class="settings-label">API Key</label>
          <input
            v-model="settings.apiKey.value"
            type="password"
            class="settings-input"
            placeholder="sk-..."
          />
        </div>
        <div class="settings-field">
          <label class="settings-label">主模型</label>
          <input
            v-model="settings.modelId.value"
            type="text"
            class="settings-input"
            placeholder="deepseek-chat"
          />
        </div>
        <div class="settings-field">
          <label class="settings-label">快速模型</label>
          <input
            v-model="settings.fastModelId.value"
            type="text"
            class="settings-input"
            placeholder="gpt-4o-mini"
          />
          <p class="settings-hint">用于深度调研单页摘要，留空则使用主模型</p>
        </div>
        <div class="settings-field">
          <label class="settings-label">角色性格</label>
          <div class="personality-options">
            <button
              v-for="opt in personalityOptions"
              :key="opt.value"
              :class="['personality-btn', { active: settings.personality.value === opt.value }]"
              @click="settings.personality.value = opt.value"
              :title="opt.description"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
        <div class="settings-field">
          <label class="settings-label">生日</label>
          <input v-model="settings.birthday.value" type="date" class="settings-input" />
        </div>
        <div class="settings-field">
          <label class="settings-label">自定义提示词</label>
          <textarea
            v-model="settings.customPrompt.value"
            class="settings-textarea"
            placeholder="留空则使用默认提示词"
            rows="4"
          />
        </div>
        <button class="settings-save-btn" @click="onSave" :disabled="settings.isSyncing.value">
          {{ settings.isSyncing.value ? '保存中...' : '保存设置' }}
        </button>
        <div v-if="saveStatus" class="settings-status" :class="{ error: saveError }">
          {{ saveStatus }}
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref } from 'vue'
import { X } from 'lucide-vue-next'
import { useSettings } from '../stores/useSettings.js'
import { personalityOptions } from '../data/personalities.js'

defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'opened'])

const settings = useSettings()
const panelEl = ref(null)
const saveStatus = ref('')
const saveError = ref(false)

defineExpose({ panelEl })

function onOpened() {
  emit('opened')
}

async function onSave() {
  saveStatus.value = ''
  saveError.value = false
  const ok = await settings.save()
  if (ok) {
    saveStatus.value = '已保存（前后端同步）'
    // Bug #20: previously the panel auto-closed 600ms after save,
    // ripping the form out from under users who wanted to continue
    // editing the next field. The user can dismiss with the X button.
  } else {
    saveError.value = true
    const detail = settings.lastSyncError.value
    saveStatus.value = detail
      ? `同步失败：${detail}`
      : '已写入本地，但同步到后端失败（请确认 desktopclaw api 已启动）'
  }
}
</script>

<style scoped>
.settings-status {
  margin-top: 6px;
  font-size: var(--font-size-xs);
  color: var(--text-muted);
}
.settings-status.error { color: var(--error); }
.settings-hint {
  font-size: var(--font-size-xs);
  color: var(--text-muted);
  line-height: 1.4;
  padding: 4px 0 2px;
}
</style>
