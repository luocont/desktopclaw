<template>
  <div :class="['collapsible-block', `collapsible-block--${blockType}`, { expanded: !collapsed }]">
    <button
      type="button"
      class="collapsible-block-header"
      :aria-expanded="!collapsed"
      @click="collapsed = !collapsed"
    >
      <component :is="icon" :size="14" class="collapsible-block-icon" />
      <span class="collapsible-block-title">{{ headerTitle }}</span>
      <ChevronDown :size="14" class="collapsible-block-chevron" />
    </button>
    <div v-show="!collapsed" class="collapsible-block-body">
      <div v-if="content" class="collapsible-block-content">{{ content }}</div>
      <div v-if="meta?.args && Object.keys(meta.args).length" class="collapsible-block-section">
        <div class="collapsible-block-label">参数</div>
        <pre class="collapsible-block-pre">{{ formatJson(meta.args) }}</pre>
      </div>
      <div v-if="meta?.result" class="collapsible-block-section">
        <div class="collapsible-block-label">结果</div>
        <pre class="collapsible-block-pre">{{ meta.result }}</pre>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Brain, Wrench, Bot, ChevronDown } from 'lucide-vue-next'

const props = defineProps({
  blockType: { type: String, required: true },
  content: { type: String, default: '' },
  meta: { type: Object, default: () => ({}) },
  defaultCollapsed: { type: Boolean, default: true },
})

const collapsed = ref(props.defaultCollapsed)

watch(
  () => props.defaultCollapsed,
  (value) => {
    collapsed.value = value
  },
)

const icon = computed(() => {
  if (props.blockType === 'thinking') return Brain
  if (props.blockType === 'subagent') return Bot
  return Wrench
})

const headerTitle = computed(() => {
  if (props.blockType === 'thinking') return '思考过程'
  if (props.blockType === 'subagent') {
    return props.meta?.label ? `子任务: ${props.meta.label}` : (props.content || '子 Agent')
  }
  if (props.blockType === 'tool') {
    return props.meta?.name ? `工具: ${props.meta.name}` : (props.content || '工具调用')
  }
  return props.content || '详情'
})

function formatJson(value) {
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
</script>
