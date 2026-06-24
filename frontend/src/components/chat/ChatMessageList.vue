<template>
  <div class="chat-message-list" ref="listEl">
    <div class="chat-message-column">
      <MessageBubble
        v-for="(msg, index) in chat.messages.value"
        :key="index"
        :message="msg"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import MessageBubble from '../MessageBubble.vue'
import { useChat } from '../../stores/useChat.js'

const chat = useChat()
const listEl = ref(null)

watch(listEl, (el) => {
  chat.messagesRef.value = el
}, { immediate: true })
</script>
