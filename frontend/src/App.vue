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

  <!-- Live2D 模型容器 -->
  <div
    ref="live2dContainer"
    class="live2d-float-container"
    :style="{ right: right + 'px', top: top + 'px' }"
    @mousedown="startDrag"
  >
    <canvas ref="live2dCanvas" id="live2d-canvas"></canvas>
    <div v-if="!isModelLoaded" class="live2d-loading">加载中...</div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted, onUnmounted } from "vue";
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display/cubism4';

// 消息列表
const messages = ref([]);
const inputValue = ref("");
const loading = ref(false);
const messagesRef = ref(null);
const eventSource = ref(null);
const feishuConnected = ref(false);
const processedMsgIds = new Set();
const isRecording = ref(false);
const mediaRecorder = ref(null);
const audioChunks = ref([]);

// Live2D 相关
const live2dContainer = ref(null);
const live2dCanvas = ref(null);
const isModelLoaded = ref(false);
let app = null;
let model = null;

// 拖动相关
const isDragging = ref(false);
const startX = ref(0);
const startY = ref(0);
const right = ref(20);
const top = ref(20);

const API_URL = "http://127.0.0.1:3000";

// 等待 Cubism Core 加载完成
function waitForCubismCore() {
  return new Promise((resolve, reject) => {
    const maxAttempts = 50;
    let attempts = 0;

    const checkInterval = setInterval(() => {
      attempts++;
      
      if (typeof Live2DCubismCore !== 'undefined') {
        clearInterval(checkInterval);
        console.log('✅ Live2D Cubism Core 已加载');
        resolve();
      } else if (attempts >= maxAttempts) {
        clearInterval(checkInterval);
        reject(new Error('Live2D Cubism Core 加载超时'));
      }
    }, 100);
  });
}

// 初始化 Live2D
async function initLive2D() {
  try {
    console.log('🚀 开始初始化 Live2D...');
    
    await waitForCubismCore();
    
    if (!live2dCanvas.value) {
      throw new Error('Canvas 元素不存在');
    }
    
    app = new PIXI.Application({
      view: live2dCanvas.value,
      width: 300,
      height: 400,
      transparent: true,
      backgroundColor: 0x000000,
      backgroundAlpha: 0,
      clearBeforeRender: true,
      preserveDrawingBuffer: false,
      antialias: true,
      resolution: window.devicePixelRatio || 1,
      autoDensity: true
    });
    
    window.PIXI = PIXI;
    
    console.log('✅ PIXI 应用已创建');
    
    const modelUrl = '/Haru/Haru.model3.json';
    console.log('📦 开始加载模型:', modelUrl);
    
    model = await Live2DModel.from(modelUrl);
    
    console.log('✅ 模型加载完成');
    
    updateModelScale();
    app.stage.addChild(model);
    
    isModelLoaded.value = true;
    console.log('✅ Live2D 初始化完成！');
    
    playStartupAnimation();
    playIdleAnimation();
    setupModelInteraction();
    
  } catch (error) {
    console.error('❌ Live2D 初始化失败:', error);
  }
}

function updateModelScale() {
  if (!model) return;
  
  const containerHeight = 400;
  const targetHeight = containerHeight * 0.9;
  const modelOriginalHeight = model.height / model.scale.y;
  const scale = targetHeight / modelOriginalHeight;
  
  model.scale.set(scale);
  model.x = (300 - model.width) / 2;
  model.y = (containerHeight - model.height) / 2;
}

function playStartupAnimation() {
  try {
    if (!model) return;
    
    const expressions = ['F01', 'F02', 'F03', 'F04', 'F05', 'F06', 'F07', 'F08'];
    const randomExpression = expressions[Math.floor(Math.random() * expressions.length)];
    
    if (model.motion) {
      model.motion('Idle', 0, 3);
    }
    
    setTimeout(() => {
      if (model && model.expression) {
        model.expression(randomExpression);
      }
    }, 500);
    
    setTimeout(() => {
      if (model && model.expression) {
        model.expression('F01');
      }
    }, 2000);
    
  } catch (error) {
    console.error('播放启动动画失败:', error);
  }
}

let idleAnimationInterval = null;
function playIdleAnimation() {
  try {
    if (!model) return;
    
    const idleActions = [
      { motion: 'Idle', expression: 'F01' },
      { motion: 'Idle', expression: 'F02' },
      { motion: 'Idle', expression: 'F03' },
      { motion: 'Idle', expression: 'F04' }
    ];
    
    let currentActionIndex = 0;
    
    const playCurrentIdleAction = () => {
      if (!model) return;
      
      const currentAction = idleActions[currentActionIndex];
      
      try {
        if (model.motion) {
          model.motion(currentAction.motion, Math.floor(Math.random() * 2), 1);
        }
        
        setTimeout(() => {
          if (model && model.expression) {
            model.expression(currentAction.expression);
          }
        }, 500);
        
      } catch (error) {
        console.warn('播放待机动作失败:', error);
      }
      
      currentActionIndex = (currentActionIndex + 1) % idleActions.length;
    };
    
    playCurrentIdleAction();
    
    idleAnimationInterval = setInterval(() => {
      if (model) {
        playCurrentIdleAction();
      } else {
        clearInterval(idleAnimationInterval);
      }
    }, 10000);
    
  } catch (error) {
    console.warn('播放待机动画失败:', error);
  }
}

function setupModelInteraction() {
  if (!model) return;
  
  model.eventMode = 'static';
  model.cursor = 'pointer';
  
  model.on('pointerdown', () => {
    playRandomMotion();
  });
}

function playRandomMotion() {
  try {
    if (!model) return;
    
    const expressions = ['F01', 'F02', 'F03', 'F04', 'F05', 'F06', 'F07', 'F08'];
    const randomExpression = expressions[Math.floor(Math.random() * expressions.length)];
    
    if (model.motion) {
      const motionIndex = Math.floor(Math.random() * 4);
      model.motion('TapBody', motionIndex, 3);
      
      setTimeout(() => {
        if (model && model.expression) {
          model.expression(randomExpression);
        }
      }, 300);
      
      setTimeout(() => {
        if (model && model.expression) {
          model.expression('F01');
        }
      }, 2500);
    }
  } catch (error) {
    console.warn('播放交互动画失败:', error);
  }
}

function cleanupLive2D() {
  if (idleAnimationInterval) {
    clearInterval(idleAnimationInterval);
    idleAnimationInterval = null;
  }
  
  if (model) {
    model.destroy();
    model = null;
  }
  
  if (app) {
    app.destroy(true);
    app = null;
  }
  
  isModelLoaded.value = false;
}

const startDrag = (e) => {
  isDragging.value = true;
  const container = live2dContainer.value;
  const rect = container.getBoundingClientRect();
  startX.value = e.clientX - (window.innerWidth - right.value - rect.width);
  startY.value = e.clientY - top.value;
  e.stopPropagation();
};

const onMouseMove = (e) => {
  if (!isDragging.value) return;
  const container = live2dContainer.value;
  const rect = container ? container.getBoundingClientRect() : { width: 300, height: 400 };
  right.value = window.innerWidth - (e.clientX - startX.value) - rect.width;
  top.value = e.clientY - startY.value;
  right.value = Math.max(10, Math.min(right.value, window.innerWidth - rect.width - 20));
  top.value = Math.max(10, Math.min(top.value, window.innerHeight - rect.height - 20));
};

const onMouseUp = () => {
  isDragging.value = false;
};

onMounted(() => {
  connectFeishuSSE();
  setTimeout(initLive2D, 500);
  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
});

onUnmounted(() => {
  disconnectFeishuSSE();
  cleanupLive2D();
  window.removeEventListener('mousemove', onMouseMove);
  window.removeEventListener('mouseup', onMouseUp);
});

const connectFeishuSSE = async () => {
  if (window.electronAPI && window.electronAPI.removeFeishuListener) {
    window.electronAPI.removeFeishuListener();
  }

  if (eventSource.value) {
    eventSource.value.close();
    eventSource.value = null;
  }

  if (window.electronAPI && window.electronAPI.connectFeishuSSE) {
    console.log("使用 Electron IPC 连接飞书 SSE");
    try {
      await window.electronAPI.connectFeishuSSE();
      feishuConnected.value = true;
      console.log("飞书 SSE 已连接");

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

const handleFeishuEvent = async (data) => {
  if (!data || !data.msgId) return;

  if (processedMsgIds.has(data.msgId)) {
    return;
  }
  processedMsgIds.add(data.msgId);

  if (processedMsgIds.size > 1000) {
    const firstItem = processedMsgIds.values().next().value;
    processedMsgIds.delete(firstItem);
  }

  if (data.msgType === "text" && data.content) {
    const userMessage = data.content;

    messages.value.push({
      role: "user",
      content: userMessage,
    });

    await nextTick();
    scrollToBottom();

    await sendToAI(userMessage);
  }
};

const disconnectFeishuSSE = () => {
  if (window.electronAPI && window.electronAPI.removeFeishuListener) {
    window.electronAPI.removeFeishuListener();
  }

  if (eventSource.value) {
    eventSource.value.close();
    eventSource.value = null;
  }
  feishuConnected.value = false;
};

const sendMessage = async () => {
  const message = inputValue.value.trim();
  if (!message || loading.value) return;

  messages.value.push({
    role: "user",
    content: message,
  });

  inputValue.value = "";
  await nextTick();
  scrollToBottom();

  await sendToAI(message);
};

const sendToAI = async (message) => {
  loading.value = true;

  const thinkingMsg = { role: "ai", content: "思考中...", isThinking: true };
  messages.value.push(thinkingMsg);
  await nextTick();
  scrollToBottom();

  try {
    const response = await fetch(`${API_URL}/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message }),
    });

    const thinkingIndex = messages.value.findIndex((m) => m.isThinking);
    if (thinkingIndex !== -1) {
      messages.value.splice(thinkingIndex, 1);
    }

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    if (data.success) {
      messages.value.push({
        role: "ai",
        content: data.response,
      });
    } else {
      messages.value.push({
        role: "ai",
        content: "抱歉，处理消息时出现错误: " + (data.error || "未知错误"),
      });
    }
  } catch (error) {
    console.error("发送消息失败:", error);

    const thinkingIndex = messages.value.findIndex((m) => m.isThinking);
    if (thinkingIndex !== -1) {
      messages.value.splice(thinkingIndex, 1);
    }

    messages.value.push({
      role: "ai",
      content: "抱歉，连接服务器失败，请检查网络或稍后重试。",
    });
  } finally {
    loading.value = false;
    await nextTick();
    scrollToBottom();
  }
};

const scrollToBottom = () => {
  if (messagesRef.value) {
    messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
  }
};

const startRecording = async () => {
  if (isRecording.value) return;

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
      const audioBlob = new Blob(audioChunks.value, { type: "audio/webm" });
      await uploadAudio(audioBlob);

      stream.getTracks().forEach((track) => track.stop());
    };

    mediaRecorder.value.start();
    isRecording.value = true;
  } catch (error) {
    console.error("开始录音失败:", error);
    alert("无法访问麦克风，请检查权限设置");
  }
};

const stopRecording = () => {
  if (!isRecording.value || !mediaRecorder.value) return;

  if (mediaRecorder.value.state !== "inactive") {
    mediaRecorder.value.stop();
  }
  isRecording.value = false;
};

const uploadAudio = async (audioBlob) => {
  loading.value = true;

  const thinkingMsg = { role: "ai", content: "识别语音中...", isThinking: true };
  messages.value.push(thinkingMsg);
  await nextTick();
  scrollToBottom();

  try {
    const formData = new FormData();
    formData.append("audio", audioBlob, "recording.webm");

    const response = await fetch(`${API_URL}/speech-to-text`, {
      method: "POST",
      body: formData,
    });

    const thinkingIndex = messages.value.findIndex((m) => m.isThinking);
    if (thinkingIndex !== -1) {
      messages.value.splice(thinkingIndex, 1);
    }

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const data = await response.json();

    if (data.success && data.text) {
      messages.value.push({
        role: "user",
        content: data.text,
        audioPath: data.audioPath,
      });

      await nextTick();
      scrollToBottom();

      await sendToAI(data.text);
    } else {
      messages.value.push({
        role: "ai",
        content: "语音识别失败: " + (data.error || "无法识别语音内容"),
      });
    }
  } catch (error) {
    console.error("上传音频失败:", error);

    const thinkingIndex = messages.value.findIndex((m) => m.isThinking);
    if (thinkingIndex !== -1) {
      messages.value.splice(thinkingIndex, 1);
    }

    messages.value.push({
      role: "ai",
      content: "语音处理失败，请检查网络或稍后重试。",
    });
  } finally {
    loading.value = false;
    await nextTick();
    scrollToBottom();
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

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
}

.thinking-dots {
  font-style: italic;
  color: #666;
}

.audio-message {
  display: flex;
  align-items: center;
  gap: 8px;
}

.audio-icon {
  font-size: 16px;
}

.audio-player {
  max-width: 200px;
  height: 30px;
}

.input-area {
  display: flex;
  gap: 10px;
  align-items: center;
}

.input-field {
  flex: 1;
  padding: 12px;
  border: 1px solid #ddd;
  border-radius: 20px;
  font-size: 14px;
  outline: none;
}

.input-field:focus {
  border-color: #007bff;
}

.input-field:disabled {
  background: #f0f0f0;
  cursor: not-allowed;
}

.send-button {
  padding: 12px 24px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.send-button:hover:not(:disabled) {
  background: #0056b3;
}

.send-button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.record-button {
  padding: 12px 20px;
  background: #28a745;
  color: white;
  border: none;
  border-radius: 20px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
  white-space: nowrap;
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
  0%, 100% {
    opacity: 1;
  }
  50% {
    opacity: 0.7;
  }
}

/* Live2D 浮动容器样式 */
.live2d-float-container {
  position: fixed;
  width: 300px;
  height: 400px;
  z-index: 1000;
  cursor: grab;
  user-select: none;
  -webkit-user-select: none;
  background: transparent;
}

.live2d-float-container:active {
  cursor: grabbing;
}

.live2d-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #666;
  font-size: 14px;
  background: rgba(255, 255, 255, 0.9);
  padding: 10px 20px;
  border-radius: 20px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
}

#live2d-canvas {
  width: 100%;
  height: 100%;
  display: block;
}
</style>