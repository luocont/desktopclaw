<template>
  <div :class="['bubble-message', message.role === 'user' ? 'bubble-user' : 'bubble-ai']">
    <div class="bubble-message-content">
      <template v-if="message.isToolCall">
        <div class="tool-call-indicator">
          <Wrench :size="14" class="tool-icon" />
          <span class="tool-text">{{ message.content }}</span>
        </div>
      </template>
      <template v-else-if="message.isThinking">
        <div class="thinking-indicator">
          <span class="thinking-dots">{{ message.content }}</span>
        </div>
      </template>
      <template v-else-if="message.audioPath">
        <div class="audio-message">
          <Mic :size="16" class="audio-icon" />
          <audio controls class="audio-player">
            <source :src="message.audioPath" type="audio/ogg; codecs=opus" />
          </audio>
        </div>
      </template>
      <template v-else-if="message.ttsAudioPath">
        <div class="tts-message">
          <Volume2 :size="16" class="tts-icon" />
          <audio controls class="audio-player">
            <source :src="message.ttsAudioPath" type="audio/mpeg" />
          </audio>
        </div>
      </template>
      <template v-else-if="message.role === 'ai'">
        <div class="markdown-body" v-html="renderMarkdown(message.content)"></div>
      </template>
      <template v-else>{{ message.content }}</template>
    </div>
  </div>
</template>

<script setup>
import { Wrench, Mic, Volume2 } from 'lucide-vue-next'
import { renderMarkdown } from '../utils/markdown.js'

defineProps({
  message: { type: Object, required: true },
})
</script>
