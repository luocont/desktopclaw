<template>

  <transition name="picker-fade" @after-enter="onOpened">

    <div v-if="visible" ref="panelEl" class="settings-panel glass-card" @click.stop>

      <div class="picker-header">

        <span>设置</span>

        <button class="picker-close" @click="$emit('close')" aria-label="关闭设置">

          <X :size="14" />

        </button>

      </div>

      <SettingsForm

        :show-memory-button="false"

        :show-switch-to-chat="true"

        @switch-to-chat="$emit('close')"

      />

    </div>

  </transition>

</template>



<script setup>

import { ref } from 'vue'

import { X } from 'lucide-vue-next'

import SettingsForm from './settings/SettingsForm.vue'



defineProps({

  visible: { type: Boolean, default: false },

})

const emit = defineEmits(['close', 'opened'])



const panelEl = ref(null)



defineExpose({ panelEl })



function onOpened() {

  emit('opened')

}

</script>



<style scoped>

.settings-panel :deep(.settings-form) {

  padding: var(--space-md);

  display: flex;

  flex-direction: column;

  gap: var(--space-md);

  flex: 1;

  min-height: 0;

  overflow-y: auto;

  background: var(--bg-secondary);

}



.settings-panel :deep(.settings-page-field) {

  display: flex;

  flex-direction: column;

  gap: 6px;

}



.settings-panel :deep(.settings-page-label) {

  font-size: var(--font-size-sm);

  font-weight: 600;

  color: var(--text-secondary);

}



.settings-panel :deep(.settings-page-hint) {

  font-size: var(--font-size-xs);

  color: var(--text-muted);

  margin: 0;

  line-height: 1.4;

}



.settings-panel :deep(.settings-page-input),

.settings-panel :deep(.settings-page-textarea) {

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



.settings-panel :deep(.settings-page-textarea) {

  resize: vertical;

}



.settings-panel :deep(.settings-page-input:focus),

.settings-panel :deep(.settings-page-textarea:focus) {

  border-color: var(--accent-amber);

}



.settings-panel :deep(.settings-page-personality) {

  display: flex;

  gap: var(--space-sm);

}



.settings-panel :deep(.settings-page-personality-btn) {

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



.settings-panel :deep(.settings-page-personality-btn:hover) {

  background: var(--glass-bg-strong);

  border-color: var(--accent-amber);

}



.settings-panel :deep(.settings-page-personality-btn.active) {

  background: var(--accent-amber);

  color: white;

  border-color: var(--accent-amber);

}



.settings-panel :deep(.settings-page-secondary-btn) {

  padding: 8px 16px;

  background: transparent;

  color: var(--text-secondary);

  border: 1px solid var(--glass-border);

  border-radius: var(--radius-md);

  font-size: var(--font-size-sm);

  cursor: pointer;

  transition: background 0.2s ease;

}



.settings-panel :deep(.settings-page-secondary-btn:hover) {

  background: var(--glass-bg-strong);

}



.settings-panel :deep(.settings-page-save-btn) {

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



.settings-panel :deep(.settings-page-save-btn:hover) {

  opacity: 0.85;

}



.settings-panel :deep(.settings-page-save-btn:disabled) {

  opacity: 0.5;

  cursor: not-allowed;

}



.settings-panel :deep(.settings-page-status) {

  margin-top: 6px;

  font-size: var(--font-size-xs);

  color: var(--text-muted);

}



.settings-panel :deep(.settings-page-status.error) {

  color: var(--error);

}

</style>

