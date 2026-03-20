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
          <template v-else-if="msg.audioPath">
            <div class="audio-message">
              <span class="audio-icon">🎤</span>
              <audio controls class="audio-player">
                <source :src="msg.audioPath" type="audio/ogg; codecs=opus">
                您的浏览器不支持音频播放
              </audio>
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
        :disabled="loading || isRecording"
        class="input-field"
      />
      <button
        @click="sendMessage"
        :disabled="loading || !inputValue.trim() || isRecording"
        class="send-button"
      >
        {{ loading ? "处理中..." : "发送" }}
      </button>
      <button
        @mousedown="startRecording"
        @mouseup="stopRecording"
        @mouseleave="stopRecording"
        @touchstart.prevent="startRecording"
        @touchend.prevent="stopRecording"
        :disabled="loading"
        :class="['record-button', { 'recording': isRecording }]"
      >
        {{ isRecording ? "🔴 录音中..." : "🎤 按住说话" }}
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
// 录音状态
const isRecording = ref(false);
// 录音相关
const mediaRecorder = ref(null);
const audioChunks = ref([]);

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
    console.log("data.metadata:", data.metadata);
    console.log("data.media:", data.media);
    const msgData = {
      role: "user",
      content: data.content || "(空消息)",
    };
    if (data.metadata && data.metadata.msg_type === "audio" && data.media && data.media.length > 0) {
      const fileName = data.media[0].split('\\').pop().split('/').pop();
      msgData.audioPath = `${API_URL}/media/${fileName}`;
      console.log("音频路径:", msgData.audioPath);
      console.log("音频文件名:", fileName);
    } else {
      console.log("不是音频消息或缺少数据");
      console.log("metadata?.msg_type:", data.metadata?.msg_type);
      console.log("media?.length:", data.media?.length);
    }
    messages.value.push(msgData);
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

// 开始录音
const startRecording = async () => {
  if (isRecording.value || loading.value) return;
  
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder.value = new MediaRecorder(stream);
    audioChunks.value = [];
    
    mediaRecorder.value.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.value.push(event.data);
      }
    };
    
    mediaRecorder.value.onstop = async () => {
      const audioBlob = new Blob(audioChunks.value, { type: 'audio/webm' });
      await sendAudioMessage(audioBlob);
      
      // 停止所有轨道
      stream.getTracks().forEach(track => track.stop());
    };
    
    mediaRecorder.value.start();
    isRecording.value = true;
    console.log("开始录音");
  } catch (error) {
    console.error("录音失败:", error);
    alert("无法访问麦克风，请检查权限设置");
  }
};

// 停止录音
const stopRecording = () => {
  if (!isRecording.value || !mediaRecorder.value) return;
  
  mediaRecorder.value.stop();
  isRecording.value = false;
  console.log("停止录音");
};

// 发送音频消息
const sendAudioMessage = async (audioBlob) => {
  loading.value = true;
  
  // 添加用户音频消息到列表
  const audioUrl = URL.createObjectURL(audioBlob);
  messages.value.push({
    role: "user",
    audioPath: audioUrl,
    isLocalAudio: true,
  });
  await nextTick();
  scrollToBottom();
  
  try {
    // 创建 FormData 发送音频
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');
    formData.append('channel', 'feishu');
    
    // 发送到后端进行识别和处理
    const response = await axios.post(
      `${API_URL}/audio/upload`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 600000,
      }
    );
    
    console.log("音频处理响应:", response.data);
    
    // 显示 AI 回复
    if (response.data?.response) {
      messages.value.push({
        role: "assistant",
        content: response.data.response,
      });
      await nextTick();
      scrollToBottom();
    }
  } catch (error) {
    console.error("发送音频失败:", error);
    messages.value.push({
      role: "assistant",
      content: `❌ 音频处理失败: ${error.message || "未知错误"}`,
    });
    await nextTick();
    scrollToBottom();
  } finally {
    loading.value = false;
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

/* 音频消息样式 */
.audio-message {
  display: flex;
  align-items: center;
  gap: 10px;
}

.audio-icon {
  font-size: 20px;
}

.audio-player {
  height: 36px;
  max-width: 300px;
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

/* 录音按钮样式 */
.record-button {
  padding: 12px 20px;
  background: #28a745;
  color: white;
  border: none;
  border-radius: 25px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.3s;
  user-select: none;
  -webkit-user-select: none;
}

.record-button:hover:not(:disabled) {
  background: #218838;
}

.record-button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.record-button.recording {
  background: #dc3545;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0% {
    transform: scale(1);
  }
  50% {
    transform: scale(1.05);
  }
  100% {
    transform: scale(1);
  }
}
</style>
