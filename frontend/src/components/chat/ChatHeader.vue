<template>
  <header class="chat-header">
    <div class="chat-header-left">
      <button
        type="button"
        class="chat-icon-btn"
        aria-label="切换侧栏"
        @click="$emit('toggleSidebar')"
      >
        <PanelLeft :size="18" />
      </button>
      <span class="chat-header-title">{{ title }}</span>
    </div>
    <div class="chat-header-actions">
      <button type="button" class="chat-primary-btn" @click="$emit('openModelPicker')">
        模型
      </button>
      <button type="button" class="chat-icon-btn" aria-label="设置" @click="$emit('openSettings')">
        <Settings :size="18" />
      </button>
    </div>
  </header>
</template>

<script setup>
import { PanelLeft, Settings } from 'lucide-vue-next'

defineProps({
  title: { type: String, default: '新对话' },
})

defineEmits(['toggleSidebar', 'openSettings', 'openModelPicker'])
</script>
