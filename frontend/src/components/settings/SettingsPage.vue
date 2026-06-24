<template>
  <main class="chat-main">
    <header class="chat-header">
      <div class="chat-header-left">
        <button type="button" class="chat-icon-btn" aria-label="返回聊天" @click="$emit('back')">
          <ArrowLeft :size="18" />
        </button>
        <span class="chat-header-title">设置</span>
      </div>
    </header>
    <div class="settings-page-body">
      <SettingsForm @open-memory="$emit('openMemory')" />
    </div>
  </main>
</template>

<script setup>
import { ArrowLeft } from 'lucide-vue-next'
import SettingsForm from './SettingsForm.vue'

defineEmits(['back', 'openMemory'])
</script>
