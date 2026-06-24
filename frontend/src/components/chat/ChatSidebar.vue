<template>
  <aside class="chat-sidebar" :class="{ collapsed: !visible }">
    <div class="sidebar-brand">
      <span class="sidebar-brand-icon">🦞</span>
      <span>DesktopClaw</span>
    </div>

    <button type="button" class="sidebar-new-btn" @click="$emit('newChat')">
      <Plus :size="16" />
      <span>新对话</span>
      <span class="shortcut-hint">Ctrl K</span>
    </button>

    <div class="sidebar-section-label">历史对话</div>
    <div class="sidebar-history">
      <div
        v-for="conv in conversations.sortedList.value"
        :key="conv.id"
        :class="['sidebar-history-item', { active: conv.id === conversations.activeId.value }]"
        role="button"
        tabindex="0"
        @click="$emit('selectConversation', conv.id)"
        @keydown.enter="$emit('selectConversation', conv.id)"
      >
        <MessageSquare :size="14" />
        <span class="sidebar-history-title">{{ conv.title }}</span>
        <button
          type="button"
          class="sidebar-history-delete"
          aria-label="删除对话"
          @click.stop="$emit('deleteConversation', conv.id)"
        >
          <Trash2 :size="12" />
        </button>
      </div>
    </div>

    <div class="sidebar-footer">
      <button type="button" class="sidebar-footer-btn" @click="$emit('switchUi')">
        <Monitor :size="14" />
        <span>切换到桌面宠物</span>
      </button>
      <button
        type="button"
        :class="['sidebar-footer-btn', { active: settingsActive }]"
        @click="$emit('openSettings')"
      >
        <Settings :size="14" />
        <span>设置</span>
      </button>
    </div>
  </aside>
</template>

<script setup>
import { Plus, MessageSquare, Trash2, Monitor, Settings } from 'lucide-vue-next'
import { useConversations } from '../../stores/useConversations.js'

defineProps({
  visible: { type: Boolean, default: true },
  settingsActive: { type: Boolean, default: false },
})

defineEmits(['newChat', 'selectConversation', 'deleteConversation', 'switchUi', 'openSettings'])

const conversations = useConversations()
</script>

<style scoped>
.shortcut-hint {
  margin-left: auto;
  font-size: 11px;
  color: var(--chat-text-muted);
}
</style>
