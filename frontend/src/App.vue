<template>
  <div class="chat-container">
    <h2 class="title">DesktopClaw AI 助手</h2>

    <!-- 模式选择区 -->
    <div class="mode-selector">
      <button
        :class="['mode-btn', { active: currentChannel === 'api' }]"
        @click="currentChannel = 'api'"
      >
        🤖 普通模式
      </button>
      <button
        :class="[
          'mode-btn',
          'feishu-btn',
          { active: currentChannel === 'feishu' },
        ]"
        @click="currentChannel = 'feishu'"
      >
        📱 飞书模式
      </button>
    </div>

    <!-- 消息展示区 -->
    <div class="messages" ref="messagesRef">
      <div
        v-for="(msg, index) in messages"
        :key="index"
        :class="[
          'message',
          msg.role === 'user' ? 'user-message' : 'ai-message',
        ]"
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
        {{ loading ? "处理中..." : "发送" }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onUnmounted, watch, computed } from "vue";
import axios from "axios";

// 消息列表 - 分离普通模式和飞书模式
const apiMessages = ref([]);
const feishuMessages = ref([]);
// 当前显示的消息列表（计算属性）
const messages = computed(() => {
  return currentChannel.value === 'feishu' ? feishuMessages.value : apiMessages.value;
});
// 输入框值
const inputValue = ref("");
// 加载状态
const loading = ref(false);
// 当前渠道
const currentChannel = ref("api");
// 消息容器引用
const messagesRef = ref(null);
// SSE 事件源
const eventSource = ref(null);
// 当前AI消息索引
const currentAiMessageIndex = ref(-1);
// 工具调用计数
const toolCallCount = ref(0);
// 飞书连接状态
const feishuConnected = ref(false);
// 已处理的飞书消息ID集合（用于去重）
const processedFeishuMsgIds = new Set();

// API 地址（后端地址）
const API_URL = "http://127.0.0.1:3000";

// 监听渠道变化
watch(currentChannel, async (newChannel, oldChannel) => {
  if (oldChannel === "feishu") {
    disconnectFeishuSSE();
  }
  if (newChannel === "feishu") {
    connectFeishuSSE();
  }
});

// 连接飞书 SSE
const connectFeishuSSE = async () => {
  // 先移除之前的监听器，避免重复注册
  if (window.electronAPI && window.electronAPI.removeFeishuListener) {
    window.electronAPI.removeFeishuListener();
  }
  
  // 关闭之前的 EventSource
  if (eventSource.value) {
    eventSource.value.close();
    eventSource.value = null;
  }

  // 优先使用 Electron IPC
  if (window.electronAPI && window.electronAPI.connectFeishuSSE) {
    console.log("使用 Electron IPC 连接飞书 SSE");
    try {
      await window.electronAPI.connectFeishuSSE();
      feishuConnected.value = true;
      console.log("飞书 SSE 已连接");
      
      // 注册事件监听
      window.electronAPI.onFeishuEvent((data) => {
        console.log("飞书事件:", data);
        handleFeishuEvent(data);
      });
    } catch (e) {
      console.error("飞书 SSE 连接失败:", e);
      feishuConnected.value = false;
    }
    return;
  }

  // 回退到浏览器 EventSource
  const es = new EventSource(`${API_URL}/feishu/events`);
  eventSource.value = es;
  feishuConnected.value = true;

  es.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data);
      console.log("飞书事件:", data);
      handleFeishuEvent(data);
    } catch (e) {
      console.error("解析飞书事件失败:", e);
    }
  };

  es.onerror = (error) => {
    console.error("飞书 SSE 错误:", error);
    feishuConnected.value = false;
  };

  es.onopen = () => {
    console.log("飞书 SSE 已连接");
    feishuConnected.value = true;
  };
};

// 处理飞书事件
const handleFeishuEvent = async (data) => {
  console.log("收到飞书事件:", data.type, "内容:", data.content);

  if (data.type === "heartbeat") {
    return;
  }

  // 只在飞书模式下显示消息，非飞书模式下丢弃
  if (currentChannel.value !== "feishu") {
    console.log("非飞书模式，丢弃飞书消息:", data.type);
    return;
  }

  // 用消息内容+类型作为去重key
  const msgKey = `${data.type}_${data.content}`;
  if (processedFeishuMsgIds.has(msgKey)) {
    console.log("消息已处理，跳过:", msgKey);
    return;
  }
  processedFeishuMsgIds.add(msgKey);

  // 限制 Set 大小，避免内存泄漏
  if (processedFeishuMsgIds.size > 100) {
    processedFeishuMsgIds.clear();
  }

  if (data.type === "inbound") {
    console.log("添加 inbound 消息到列表");
    feishuMessages.value.push({
      role: "user",
      content: data.content || "(空消息)",
      source: "feishu",
    });
    await nextTick();
    scrollToBottom();
  }

  if (data.type === "outbound") {
    console.log("添加 outbound 消息到列表");
    feishuMessages.value.push({
      role: "assistant",
      content: data.content || "(空消息)",
      source: "feishu",
    });
    await nextTick();
    scrollToBottom();
  }
};

// 断开飞书 SSE
const disconnectFeishuSSE = async () => {
  // 优先使用 Electron IPC
  if (window.electronAPI && window.electronAPI.disconnectFeishuSSE) {
    try {
      await window.electronAPI.disconnectFeishuSSE();
      if (window.electronAPI.removeFeishuListener) {
        window.electronAPI.removeFeishuListener();
      }
    } catch (e) {
      console.error("断开飞书 SSE 失败:", e);
    }
  }

  if (eventSource.value) {
    eventSource.value.close();
    eventSource.value = null;
  }
  feishuConnected.value = false;
};

// 发送消息
const sendMessage = async () => {
  const content = inputValue.value.trim();
  if (!content || loading.value) return;

  // 重置工具调用计数
  toolCallCount.value = 0;

  // 获取当前模式的消息列表
  const currentMessages = currentChannel.value === 'feishu' ? feishuMessages.value : apiMessages.value;

  // 飞书模式下，消息完全由 SSE 推送，不在发送时添加任何消息
  // 普通模式下，发送时添加用户消息
  if (currentChannel.value !== 'feishu') {
    currentMessages.push({ role: "user", content });
  }
  inputValue.value = "";
  loading.value = true;

  // 滚动到底部
  await nextTick();
  scrollToBottom();

  try {
    // 使用 SSE 流式接收响应
    await sendStreamMessage(content, currentMessages);
  } catch (error) {
    console.error("发送失败:", error);
    handleError(error, currentMessages);
  } finally {
    loading.value = false;
    await nextTick();
    scrollToBottom();
  }
};

// 发送消息到后端并获取响应（非流式，更稳定）
const sendStreamMessage = async (content, currentMessages) => {
  // 飞书模式下，消息完全由 SSE 推送，不显示任何本地状态
  if (currentChannel.value === 'feishu') {
    try {
      let response;

      // 优先使用 Electron IPC（如果在 Electron 环境中）
      if (window.electronAPI && window.electronAPI.sendMessage) {
        console.log("使用 Electron IPC 发送消息 (飞书模式)");
        const result = await window.electronAPI.sendMessage(content, currentChannel.value);
        response = { data: result };
      } else {
        // 使用 axios 发送 POST 请求
        console.log("使用 axios 发送 POST 请求 (飞书模式)");
        response = await axios.post(
          `${API_URL}/chat`,
          { message: content, channel: currentChannel.value },
          {
            headers: { "Content-Type": "application/json" },
            timeout: 600000,
          },
        );
      }
      console.log("飞书模式消息已发送，等待 SSE 推送:", response.data);
      // 飞书模式下不处理响应，完全依赖 SSE 推送
    } catch (error) {
      console.error("飞书模式发送失败:", error);
      // 显示错误消息
      feishuMessages.value.push({
        role: "assistant",
        content: `❌ 发送失败: ${error.message || "未知错误"}`,
      });
      throw error;
    }
    return;
  }

  // 普通模式：显示思考中状态
  currentAiMessageIndex.value = currentMessages.length;
  currentMessages.push({
    role: "assistant",
    content: "AI 正在思考...",
    isThinking: true,
  });

  try {
    let response;

    // 优先使用 Electron IPC（如果在 Electron 环境中）
    if (window.electronAPI && window.electronAPI.sendMessage) {
      console.log("使用 Electron IPC 发送消息");
      const result = await window.electronAPI.sendMessage(content, currentChannel.value);
      response = { data: result };
    } else {
      // 使用 axios 发送 POST 请求
      console.log("使用 axios 发送 POST 请求");
      response = await axios.post(
        `${API_URL}/chat`,
        { message: content, channel: currentChannel.value },
        {
          headers: { "Content-Type": "application/json" },
          timeout: 600000,
        },
      );
    }

    console.log("收到响应:", response.data);

    // 更新 AI 消息
    if (response.data && response.data.success) {
      currentMessages[currentAiMessageIndex.value] = {
        role: "assistant",
        content: response.data.response,
      };
    } else {
      currentMessages[currentAiMessageIndex.value] = {
        role: "assistant",
        content: "抱歉，处理请求时出错。",
      };
    }
  } catch (error) {
    console.error("请求失败:", error);
    currentMessages[currentAiMessageIndex.value] = {
      role: "assistant",
      content: `❌ 请求失败: ${error.message || "未知错误"}`,
    };
    throw error;
  }
};

// 处理错误
const handleError = (error, currentMessages) => {
  console.error("Error details:", {
    message: error.message,
    code: error.code,
    response: error.response?.data,
    status: error.response?.status,
    config: error.config,
  });
  let errorMsg = "发送失败，请检查后端服务是否已启动。";
  if (error.code === "ECONNREFUSED") {
    errorMsg = `无法连接到后端服务 (${API_URL})，请确保 backend 已启动：desktopclaw gateway --port 3000`;
  } else if (error.response) {
    errorMsg = `服务器错误: ${error.response.status} - ${JSON.stringify(error.response.data)}`;
  } else if (error.message) {
    errorMsg = `请求失败: ${error.message}`;
  }
  currentMessages.push({ role: "assistant", content: `❌ ${errorMsg}` });
};

// 滚动到底部
const scrollToBottom = () => {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
  }
};

// 组件卸载时关闭 SSE 连接
onUnmounted(() => {
  if (eventSource.value) {
    eventSource.value.close();
  }
  disconnectFeishuSSE();
});
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

.mode-selector {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
  justify-content: center;
}

.mode-btn {
  padding: 10px 20px;
  border: 1px solid #ddd;
  border-radius: 20px;
  background: white;
  color: #666;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
}

.mode-btn:hover {
  border-color: #007bff;
  color: #007bff;
}

.mode-btn.active {
  background: #007bff;
  border-color: #007bff;
  color: white;
}

.feishu-btn.active {
  background: #00a1d6;
  border-color: #00a1d6;
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
