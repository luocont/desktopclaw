<template>
  <transition name="interaction-fade">
    <div v-if="visible" class="interaction-bubble glass-card">
      <div class="interaction-message">{{ message }}</div>
      <div class="interaction-arrow"></div>
    </div>
  </transition>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  message: { type: String, default: '' },
})
</script>
