<template>
  <div class="chat-container">
    <h2 class="title">DesktopClaw AI 助手</h2>

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
import { ref, nextTick, onMounted, onUnmounted } from "vue";
import axios from "axios";

// 消息列表
const messages = ref([]);
// 输入框值
const inputValue = ref("");
// 加载状态
const loading = ref(false);
// 消息容器引用
const messagesRef = ref(null);
// SSE 事件源
const eventSource = ref(null);
// 飞书连接状态
const feishuConnected = ref(false);
// 已处理的消息ID集合（用于去重）
const processedMsgIds = new Set();

// API 地址（后端地址）
const API_URL = "http://127.0.0.1:3000";

// 初始化连接飞书 SSE
onMounted(() => {
  connectFeishuSSE();
});

// 组件卸载时关闭 SSE 连接
onUnmounted(() => {
  disconnectFeishuSSE();
});

// 连接飞书 SSE
const connectFeishuSSE = async () => {
  // 先移除之前的监听器
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

  // 用消息内容+类型+时间戳作为去重key
  const msgKey = `${data.type}_${data.content}_${data.chat_id}`;
  if (processedMsgIds.has(msgKey)) {
    console.log("消息已处理，跳过:", msgKey);
    return;
  }
  processedMsgIds.add(msgKey);

  // 限制 Set 大小，避免内存泄漏
  if (processedMsgIds.size > 100) {
    processedMsgIds.clear();
  }

  if (data.type === "inbound") {
    console.log("添加用户消息到列表");
    messages.value.push({
      role: "user",
      content: data.content || "(空消息)",
    });
    await nextTick();
    scrollToBottom();
  }

  if (data.type === "outbound") {
    console.log("添加 AI 消息到列表");
    messages.value.push({
      role: "assistant",
      content: data.content || "(空消息)",
    });
    await nextTick();
    scrollToBottom();
  }
};

// 断开飞书 SSE
const disconnectFeishuSSE = async () => {
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

  inputValue.value = "";
  loading.value = true;

  messages.value.push({
    role: "user",
    content: content,
  });
  await nextTick();
  scrollToBottom();

  try {
    let response;

    if (window.electronAPI && window.electronAPI.sendMessage) {
      console.log("使用 Electron IPC 发送消息");
      response = await window.electronAPI.sendMessage(content, "feishu");
      response = { data: response };
    } else {
      console.log("使用 axios 发送 POST 请求");
      response = await axios.post(
        `${API_URL}/chat`,
        { message: content, channel: "feishu" },
        {
          headers: { "Content-Type": "application/json" },
          timeout: 600000,
        },
      );
    }
    console.log("收到响应:", response.data);

    const aiResponse = response.data?.response || response.data?.content || "(空回复)";
    messages.value.push({
      role: "assistant",
      content: aiResponse,
    });
    await nextTick();
    scrollToBottom();
  } catch (error) {
    console.error("发送失败:", error);
    messages.value.push({
      role: "assistant",
      content: `❌ 发送失败: ${error.message || "未知错误"}`,
    });
    await nextTick();
    scrollToBottom();
  } finally {
    loading.value = false;
  }
};

// 滚动到底部
const scrollToBottom = () => {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
  }
};
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
