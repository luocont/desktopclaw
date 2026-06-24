<template>

  <div class="chat-app">

    <ChatLayout

      v-if="currentView === 'chat'"

      :sidebar-visible="sidebarVisible"

      @new-chat="onNewChat"

      @select-conversation="onSelectConversation"

      @delete-conversation="onDeleteConversation"

      @switch-ui="onSwitchUi"

      @toggle-sidebar="sidebarVisible = !sidebarVisible"

      @open-settings="currentView = 'settings'"

      @open-model-picker="showModelPicker = true"

      @message-sent="onMessageSent"

    />



    <div v-else class="chat-layout">

      <ChatSidebar

        :visible="sidebarVisible"

        :settings-active="currentView === 'settings' || currentView === 'memory'"

        @new-chat="onNewChatFromSubView"

        @select-conversation="onSelectConversationFromSubView"

        @delete-conversation="onDeleteConversation"

        @switch-ui="onSwitchUi"

        @open-settings="currentView = 'settings'"

      />

      <SettingsPage

        v-if="currentView === 'settings'"

        @back="currentView = 'chat'"

        @open-memory="currentView = 'memory'"

      />

      <MemoryPage

        v-else-if="currentView === 'memory'"

        @back="currentView = 'settings'"

      />

    </div>



    <div v-if="showModelPicker" class="chat-overlay-backdrop" @click.self="showModelPicker = false">

      <div class="chat-overlay-panel">

        <ModelPicker

          :visible="showModelPicker"

          @close="showModelPicker = false"

          @pick="onPickModel"

        />

      </div>

    </div>

  </div>

</template>



<script setup>

import { ref, watch, onMounted, onUnmounted } from 'vue'

import ChatLayout from './components/chat/ChatLayout.vue'

import ChatSidebar from './components/chat/ChatSidebar.vue'

import SettingsPage from './components/settings/SettingsPage.vue'

import MemoryPage from './components/settings/MemoryPage.vue'

import ModelPicker from './components/ModelPicker.vue'

import { useChat } from './stores/useChat.js'

import { useConversations } from './stores/useConversations.js'

import { useSettings } from './stores/useSettings.js'

import { useLive2D } from './stores/useLive2D.js'

import { callElectronApi, getElectronApi, hasElectronApi } from './utils/electronBridge.js'

import './chat-theme.css'



const chat = useChat()

const conversations = useConversations()

const settings = useSettings()

const live2d = useLive2D()



const sidebarVisible = ref(true)

const currentView = ref('chat')

const showModelPicker = ref(false)



function syncMessagesToStore(msgs) {

  chat.messages.value = msgs ? [...msgs] : []

}



function onNewChat() {

  conversations.saveCurrent(chat.messages.value)

  conversations.createNew()

  syncMessagesToStore([])

}



function onNewChatFromSubView() {

  onNewChat()

  currentView.value = 'chat'

}



function onSelectConversation(id) {

  conversations.saveCurrent(chat.messages.value)

  const msgs = conversations.switchTo(id)

  syncMessagesToStore(msgs)

}



function onSelectConversationFromSubView(id) {

  onSelectConversation(id)

  currentView.value = 'chat'

}



async function onDeleteConversation(id) {

  const wasActive = conversations.activeId.value === id

  await conversations.remove(id)

  if (wasActive) {

    const active = conversations.activeConversation.value

    syncMessagesToStore(active?.messages || [])

    if (!active) {

      conversations.createNew()

      syncMessagesToStore([])

    }

  }

}



function onMessageSent() {

  conversations.saveCurrent(chat.messages.value)

  conversations.syncSnapshot()

}



function onSwitchUi() {

  conversations.saveCurrent(chat.messages.value)

  conversations.syncSnapshot()

  callElectronApi('switchUiMode', 'pet')

}



async function onPickModel(path) {

  await live2d.switchModel(path, null, { interactive: false })

}



function onKeydown(e) {

  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {

    e.preventDefault()

    onNewChat()

    currentView.value = 'chat'

  }

}



function onRemoteChatState(snapshot) {

  if (!snapshot) return

  const changed = conversations.applyRemoteSnapshot(snapshot)

  if (changed) {

    syncMessagesToStore(conversations.hydrateActiveToChat())

  }

}



watch(

  () => chat.messages.value,

  () => {

    if (chat.loading.value) return

    conversations.saveCurrent(chat.messages.value)

  },

  { deep: true },

)



onMounted(async () => {

  settings.loadFromBackend()

  await live2d.scanModels()

  window.addEventListener('keydown', onKeydown)



  const historyMessages = await conversations.initializeHistory()

  syncMessagesToStore(historyMessages)



  if (hasElectronApi('onChatStateUpdated')) {

    getElectronApi().onChatStateUpdated(onRemoteChatState)

  }

})



onUnmounted(() => {

  window.removeEventListener('keydown', onKeydown)

  conversations.saveCurrent(chat.messages.value)

  conversations.syncSnapshot()

  if (hasElectronApi('removeChatStateListener')) {

    callElectronApi('removeChatStateListener')

  }

})

</script>



<style scoped>

.chat-overlay-panel {

  display: flex;

  gap: 16px;

}

</style>

