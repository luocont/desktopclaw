<template>
  <div class="chat-main">
    <ChatHeader
      :title="headerTitle"
      @toggle-sidebar="$emit('toggleSidebar')"
      @open-settings="$emit('openSettings')"
      @open-model-picker="$emit('openModelPicker')"
    />
    <div class="chat-body">
      <div v-if="chat.lastError.value" class="chat-error-banner" role="alert">
        <AlertCircle :size="16" />
        <span>{{ formatLlmError(chat.lastError.value) }}</span>
        <button type="button" class="chat-error-dismiss" aria-label="关闭" @click="dismissError">×</button>
      </div>
      <ChatLive2DBackground />
      <ChatEmptyState v-if="chat.messages.value.length === 0" />
      <ChatMessageList v-else />
      <ChatComposer @sent="$emit('messageSent')" />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { AlertCircle } from 'lucide-vue-next'
import ChatHeader from './ChatHeader.vue'
import ChatEmptyState from './ChatEmptyState.vue'
import ChatMessageList from './ChatMessageList.vue'
import ChatComposer from './ChatComposer.vue'
import ChatLive2DBackground from './ChatLive2DBackground.vue'
import { useChat } from '../../stores/useChat.js'
import { useConversations } from '../../stores/useConversations.js'
import { formatLlmError } from '../../utils/llmError.js'

defineEmits(['toggleSidebar', 'openSettings', 'openModelPicker', 'messageSent'])

const chat = useChat()
const conversations = useConversations()

function dismissError() {
  chat.lastError.value = ''
}

const headerTitle = computed(() => {
  const active = conversations.activeConversation.value
  return active?.title || '新对话'
})
</script>
