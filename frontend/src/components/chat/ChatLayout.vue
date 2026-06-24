<template>
  <div class="chat-layout">
    <ChatSidebar
      :visible="sidebarVisible"
      @new-chat="$emit('newChat')"
      @select-conversation="$emit('selectConversation', $event)"
      @delete-conversation="$emit('deleteConversation', $event)"
      @switch-ui="$emit('switchUi')"
      @open-settings="$emit('openSettings')"
    />
    <ChatMain
      @toggle-sidebar="$emit('toggleSidebar')"
      @open-settings="$emit('openSettings')"
      @open-model-picker="$emit('openModelPicker')"
      @message-sent="$emit('messageSent')"
    />
  </div>
</template>

<script setup>
import ChatSidebar from './ChatSidebar.vue'
import ChatMain from './ChatMain.vue'

defineProps({
  sidebarVisible: { type: Boolean, default: true },
})

defineEmits([
  'newChat',
  'selectConversation',
  'deleteConversation',
  'switchUi',
  'toggleSidebar',
  'openSettings',
  'openModelPicker',
  'messageSent',
])
</script>
