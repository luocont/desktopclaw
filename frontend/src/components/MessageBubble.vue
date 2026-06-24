<template>
  <div :class="['bubble-message', message.role === 'user' ? 'bubble-user' : 'bubble-ai', { 'bubble-error': message.isError }]">
    <div :class="['bubble-message-content', { 'bubble-block-content': isCollapsibleBlock }]">
      <template v-if="resolvedBlockType === 'thinking' && message.isThinking">
        <div class="thinking-indicator">
          <span class="thinking-dots">{{ message.content || '思考中...' }}</span>
        </div>
      </template>
      <template v-else-if="isCollapsibleBlock">
        <CollapsibleBlock
          :block-type="resolvedBlockType"
          :content="message.content"
          :meta="message.meta"
          :default-collapsed="message.collapsed !== false"
        />
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
      <template v-else-if="message.isError">
        <div class="error-indicator">
          <AlertCircle :size="16" class="error-icon" />
          <span class="error-text">{{ message.content }}</span>
        </div>
      </template>
      <template v-else-if="message.role === 'ai'">
        <div class="markdown-body" v-html="renderMarkdown(message.content)"></div>
        <div v-if="usageText" class="token-usage">{{ usageText }}</div>
      </template>
      <template v-else>{{ message.content }}</template>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { Mic, Volume2, AlertCircle } from 'lucide-vue-next'
import { renderMarkdown } from '../utils/markdown.js'
import CollapsibleBlock from './chat/CollapsibleBlock.vue'

const props = defineProps({
  message: { type: Object, required: true },
})

const SOURCE_LABELS = {
  main: '主',
  research: '研究',
  subagent: '子任务',
}

const resolvedBlockType = computed(() => {
  if (props.message.blockType) return props.message.blockType
  if (props.message.isThinking) return 'thinking'
  if (props.message.isToolCall) return 'tool'
  return props.message.role === 'ai' ? 'reply' : null
})

const isCollapsibleBlock = computed(() => {
  const type = resolvedBlockType.value
  return type === 'thinking' || type === 'tool' || type === 'subagent'
})

function formatTokenCount(value) {
  const n = Number(value) || 0
  if (n >= 1000) {
    const compact = (n / 1000).toFixed(1).replace(/\.0$/, '')
    return `${compact}k`
  }
  return String(n)
}

const usageText = computed(() => {
  const usage = props.message.usage
  if (!usage?.total_tokens) return ''

  const total = formatTokenCount(usage.total_tokens)
  const prompt = formatTokenCount(usage.prompt_tokens)
  const completion = formatTokenCount(usage.completion_tokens)

  const parts = [`${total} tokens（输入 ${prompt} / 输出 ${completion}）`]

  const breakdown = usage.breakdown || {}
  const breakdownParts = Object.entries(breakdown)
    .filter(([, data]) => (data?.total_tokens || 0) > 0)
    .map(([key, data]) => `${SOURCE_LABELS[key] || key} ${formatTokenCount(data.total_tokens)}`)

  if (breakdownParts.length > 0) {
    parts.push(breakdownParts.join(' · '))
  }

  return parts.join(' · ')
})
</script>
