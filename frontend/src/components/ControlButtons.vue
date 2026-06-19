<template>
  <div
    class="button-row"
    :style="{ transform: `translateY(-50%) scale(${scale})`, transformOrigin: 'left center' }"
  >
    <button
      class="toggle-dialog-btn"
      @click.stop="$emit('toggle', 'dialog')"
      :class="{ active: dialog }"
      title="打开对话框"
      :aria-label="dialog ? '关闭对话框' : '打开对话框'"
    >
      <MessageCircle :size="iconSize" />
    </button>
    <button
      class="model-switch-btn"
      @click.stop="$emit('toggle', 'modelPicker')"
      :class="{ active: modelPicker }"
      title="更换皮肤"
      :aria-label="modelPicker ? '关闭皮肤选择' : '打开皮肤选择'"
    >
      <Palette :size="iconSize" />
    </button>
    <button
      class="settings-btn"
      @click.stop="$emit('toggle', 'settings')"
      :class="{ active: settings }"
      title="设置"
      :aria-label="settings ? '关闭设置' : '打开设置'"
    >
      <Settings :size="iconSize" />
    </button>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { MessageCircle, Palette, Settings } from 'lucide-vue-next'

const props = defineProps({
  scale: { type: Number, default: 1 },
  dialog: { type: Boolean, default: false },
  modelPicker: { type: Boolean, default: false },
  settings: { type: Boolean, default: false },
})
defineEmits(['toggle'])

const iconSize = computed(() => Math.round(20 * props.scale))
</script>
