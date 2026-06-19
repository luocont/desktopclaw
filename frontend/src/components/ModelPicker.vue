<template>
  <transition name="picker-fade" @after-enter="onOpened">
    <div v-if="visible" ref="panelEl" class="model-picker glass-card" @click.stop>
      <div class="picker-header">
        <span>选择皮肤</span>
        <button class="picker-close" @click="$emit('close')" aria-label="关闭皮肤选择">
          <X :size="14" />
        </button>
      </div>
      <div class="picker-list">
        <div
          v-for="m in live2d.availableModels.value"
          :key="m.path"
          :class="['picker-item', { active: live2d.currentModelUrl.value === m.path }]"
          @click="onPick(m.path)"
        >
          <Palette :size="16" class="picker-item-icon" />
          <span class="picker-item-name">{{ m.name }}</span>
          <Check v-if="live2d.currentModelUrl.value === m.path" :size="16" class="picker-check" />
        </div>
        <div v-if="live2d.availableModels.value.length === 0" class="picker-empty">
          暂无可用皮肤
        </div>
      </div>
    </div>
  </transition>
</template>

<script setup>
import { ref } from 'vue'
import { X, Palette, Check } from 'lucide-vue-next'
import { useLive2D } from '../stores/useLive2D.js'

defineProps({
  visible: { type: Boolean, default: false },
})
const emit = defineEmits(['close', 'pick', 'opened'])

const live2d = useLive2D()
const panelEl = ref(null)

defineExpose({ panelEl })

function onOpened() {
  emit('opened')
}

function onPick(path) {
  emit('pick', path)
  emit('close')
}
</script>
