<template>
  <div class="chat-container">
    <h2 class="title">DesktopClaw AI 助手</h2>

    <!-- 消息展示区 -->
    <div class="messages" ref="messagesRef">
      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="['message', msg.role === 'user' ? 'user-message' : 'ai-message']"
      >
        <div class="message-content">
          <template v-if="msg.isToolCall">
            <div class="tool-call-indicator">
              <span class="tool-icon">🔧</span>
              <span class="tool-text">{{ msg.content }}</span>
            </div>
          </template>
          <template v-else-if="msg.isThinking">
            <div class="thinking-indicator">
              <span class="thinking-dots">{{ msg.content }}</span>
            </div>
          </template>
          <template v-else>{{ msg.content }}</template>
        </div>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="input-area">
      <input
        v-model="inputValue"
        @keyup.enter="sendMessage"
        placeholder="请输入要发送的内容..."
        :disabled="loading"
        class="input-field"
      />
      <button
        @click="sendMessage"
        :disabled="loading || !inputValue.trim()"
        class="send-button"
      >
        {{ loading ? '处理中...' : '发送' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onUnmounted } from 'vue'
import axios from 'axios'

// 消息列表
const messages = ref([])
// 输入框值
const inputValue = ref('')
// 加载状态
const loading = ref(false)
// 消息容器引用
const messagesRef = ref(null)
// SSE 事件源
const eventSource = ref(null)
// 当前AI消息索引
const currentAiMessageIndex = ref(-1)
// 工具调用计数
const toolCallCount = ref(0)

// API 地址（后端地址）
const API_URL = 'http://127.0.0.1:3000'

// 发送消息
const sendMessage = async () => {
  const content = inputValue.value.trim()
  if (!content || loading.value) return

  // 重置工具调用计数
  toolCallCount.value = 0

  // 添加用户消息到列表
  messages.value.push({ role: 'user', content })
  inputValue.value = ''
  loading.value = true

  // 滚动到底部
  await nextTick()
  scrollToBottom()

  try {
    // 使用 SSE 流式接收响应
    await sendStreamMessage(content)
  } catch (error) {
    console.error('发送失败:', error)
    handleError(error)
  } finally {
    loading.value = false
    await nextTick()
    scrollToBottom()
  }
}

// 发送消息到后端并获取响应（非流式，更稳定）
const sendStreamMessage = async (content) => {
  // 显示思考中状态
  currentAiMessageIndex.value = messages.value.length
  messages.value.push({
    role: 'assistant',
    content: 'AI 正在思考...',
    isThinking: true
  })

  try {
    let response

    // 优先使用 Electron IPC（如果在 Electron 环境中）
    if (window.electronAPI && window.electronAPI.sendMessage) {
      console.log('使用 Electron IPC 发送消息')
      const result = await window.electronAPI.sendMessage(content)
      response = { data: result }
    } else {
      // 使用 axios 发送 POST 请求
      console.log('使用 axios 发送 POST 请求')
      response = await axios.post(`${API_URL}/chat`, {
        message: content
      }, {
        headers: {
          'Content-Type': 'application/json'
        },
        timeout: 600000 // 10分钟超时
      })
    }

    console.log('收到响应:', response.data)

    // 更新 AI 消息
    if (response.data && response.data.success) {
      messages.value[currentAiMessageIndex.value] = {
        role: 'assistant',
        content: response.data.response
      }
    } else {
      messages.value[currentAiMessageIndex.value] = {
        role: 'assistant',
        content: '抱歉，处理请求时出错。'
      }
    }
  } catch (error) {
    console.error('请求失败:', error)
    messages.value[currentAiMessageIndex.value] = {
      role: 'assistant',
      content: `❌ 请求失败: ${error.message || '未知错误'}`
    }
    throw error
  }
}

// 处理错误
const handleError = (error) => {
  console.error('Error details:', {
    message: error.message,
    code: error.code,
    response: error.response?.data,
    status: error.response?.status,
    config: error.config
  })
  let errorMsg = '发送失败，请检查后端服务是否已启动。'
  if (error.code === 'ECONNREFUSED') {
    errorMsg = `无法连接到后端服务 (${API_URL})，请确保 backend 已启动：desktopclaw gateway --port 3000`
  } else if (error.response) {
    errorMsg = `服务器错误: ${error.response.status} - ${JSON.stringify(error.response.data)}`
  } else if (error.message) {
    errorMsg = `请求失败: ${error.message}`
  }
  messages.value.push({ role: 'assistant', content: `❌ ${errorMsg}` })
}

// 滚动到底部
const scrollToBottom = () => {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight
  }
}

// 组件卸载时关闭 SSE 连接
onUnmounted(() => {
  if (eventSource.value) {
    eventSource.value.close()
  }
})
</script>

<style scoped>
.chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  box-sizing: border-box;
}

.title {
  text-align: center;
  color: #333;
  margin-bottom: 20px;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  background: #f5f5f5;
  border-radius: 8px;
  margin-bottom: 20px;
}

.message {
  margin-bottom: 15px;
  max-width: 80%;
}

.user-message {
  margin-left: auto;
  text-align: right;
}

.ai-message {
  margin-right: auto;
}

.message-content {
  display: inline-block;
  padding: 10px 15px;
  border-radius: 15px;
  word-wrap: break-word;
  text-align: left;
}

.user-message .message-content {
  background: #007bff;
  color: white;
}

.ai-message .message-content {
  background: white;
  color: #333;
  border: 1px solid #ddd;
}

.loading .message-content {
  background: #f0f0f0;
  color: #666;
  font-style: italic;
}

/* 工具调用样式 */
.tool-call-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #666;
}

.tool-icon {
  font-size: 14px;
}

.tool-text {
  font-family: monospace;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
}

/* 思考中样式 */
.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.thinking-dots {
  font-style: italic;
  color: #666;
}

.input-area {
  display: flex;
  gap: 10px;
}

.input-field {
  flex: 1;
  padding: 12px 15px;
  border: 1px solid #ddd;
  border-radius: 25px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.3s;
}

.input-field:focus {
  border-color: #007bff;
}

.input-field:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.send-button {
  padding: 12px 25px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 25px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.3s;
}

.send-button:hover:not(:disabled) {
  background: #0056b3;
}

.send-button:disabled {
  background: #ccc;
  cursor: not-allowed;
}
</style>
