<template>
  <div class="desktop-pet-wrapper">
    <div
      class="pet-container"
      ref="petContainer"
      :style="petContainerStyle"
      @mouseenter="onPetAreaEnter"
      @mouseleave="onPetAreaLeave"
    >
      <transition name="bubble-fade">
        <div
          v-show="showDialog"
          class="dialog-bubble"
          ref="dialogBubble"
        >
          <div class="bubble-header">
            <span class="bubble-title">DesktopClaw</span>
            <button class="bubble-close" @click="showDialog = false">✕</button>
          </div>
          <div class="bubble-messages" ref="messagesRef">
            <div
              v-for="(msg, index) in messages"
              :key="index"
              :class="[
                'bubble-message',
                msg.role === 'user' ? 'bubble-user' : 'bubble-ai',
              ]"
            >
              <div class="bubble-message-content">
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
                    </audio>
                  </div>
                </template>
                <template v-else-if="msg.ttsAudioPath">
                  <div class="tts-message">
                    <span class="tts-icon">🔊</span>
                    <audio controls class="audio-player">
                      <source :src="msg.ttsAudioPath" type="audio/mpeg">
                    </audio>
                  </div>
                </template>
                <template v-else-if="msg.role === 'ai' || msg.role === 'assistant'">
                  <div class="markdown-body" v-html="renderMarkdown(msg.content)"></div>
                </template>
                <template v-else>{{ msg.content }}</template>
              </div>
            </div>
          </div>
          <div class="bubble-input">
            <input
              v-model="inputValue"
              @keyup.enter="sendMessage"
              placeholder="和我说点什么..."
              :disabled="loading || isRecording"
              class="bubble-input-field"
            />
            <button
              @click="sendMessage"
              :disabled="loading || !inputValue.trim() || isRecording"
              class="bubble-send-btn"
            >
              {{ loading ? "..." : "➤" }}
            </button>
            <button
              @mousedown="startRecording"
              @mouseup="stopRecording"
              @mouseleave="stopRecording"
              @touchstart.prevent="startRecording"
              @touchend.prevent="stopRecording"
              :disabled="loading"
              :class="['bubble-record-btn', { recording: isRecording }]"
            >
              🎤
            </button>
          </div>
          <div class="bubble-arrow"></div>
        </div>
      </transition>

      <div
        class="live2d-wrapper"
        @mousedown="startDrag"
      >
        <canvas ref="live2dCanvas" id="live2d-canvas"></canvas>
        <div v-if="!isModelLoaded" class="live2d-loading">加载中...</div>
      </div>

      <button
        class="toggle-dialog-btn"
        @click.stop="showDialog = !showDialog"
        :class="{ active: showDialog }"
        title="打开对话框"
      >
        <span class="btn-icon">💬</span>
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted } from "vue";
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display/cubism4';
import axios from 'axios';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

marked.setOptions({
  breaks: true,
  gfm: true,
});

function renderMarkdown(content) {
  if (!content) return '';
  const rawHtml = marked.parse(content);
  return DOMPurify.sanitize(rawHtml);
}

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

const showDialog = ref(false);
const dialogBubble = ref(null);
const petContainer = ref(null);

const live2dCanvas = ref(null);
const isModelLoaded = ref(false);
let app = null;
let model = null;

const isDragging = ref(false);
const dragMoved = ref(false);
const startX = ref(0);
const startY = ref(0);
const petX = ref(window.innerWidth - 320);
const petY = ref(window.innerHeight - 450);

const isHoveringPet = ref(false);

const API_URL = "http://127.0.0.1:3000";

const petContainerStyle = computed(() => ({
  left: petX.value + 'px',
  top: petY.value + 'px',
}));

function onPetAreaEnter() {
  isHoveringPet.value = true;
  setClickThrough(false);
}

function onPetAreaLeave() {
  isHoveringPet.value = false;
  if (!isDragging.value) {
    setClickThrough(true);
  }
}

function setClickThrough(ignore) {
  if (window.electronAPI && window.electronAPI.setIgnoreMouseEvents) {
    window.electronAPI.setIgnoreMouseEvents(ignore, { forward: true });
  }
}

function waitForCubismCore() {
  return new Promise((resolve, reject) => {
    const maxAttempts = 50;
    let attempts = 0;

    const checkInterval = setInterval(() => {
      attempts++;
      if (typeof Live2DCubismCore !== 'undefined') {
        clearInterval(checkInterval);
        resolve();
      } else if (attempts >= maxAttempts) {
        clearInterval(checkInterval);
        reject(new Error('Live2D Cubism Core 加载超时'));
      }
    }, 100);
  });
}

async function initLive2D() {
  try {
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

    const modelUrl = '/Haru/Haru.model3.json';
    model = await Live2DModel.from(modelUrl);

    updateModelScale();
    app.stage.addChild(model);

    isModelLoaded.value = true;

    playStartupAnimation();
    playIdleAnimation();
    setupModelInteraction();

  } catch (error) {
    console.error('Live2D 初始化失败:', error);
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
  dragMoved.value = false;
  startX.value = e.clientX - petX.value;
  startY.value = e.clientY - petY.value;
  e.preventDefault();
};

const onMouseMove = (e) => {
  if (!isDragging.value) return;
  dragMoved.value = true;

  let newX = e.clientX - startX.value;
  let newY = e.clientY - startY.value;

  newX = Math.max(0, Math.min(newX, window.innerWidth - 340));
  newY = Math.max(0, Math.min(newY, window.innerHeight - 440));

  petX.value = newX;
  petY.value = newY;
};

const onMouseUp = () => {
  isDragging.value = false;
};

const connectFeishuSSE = async () => {
  if (window.electronAPI && window.electronAPI.removeFeishuListener) {
    window.electronAPI.removeFeishuListener();
  }

  if (eventSource.value) {
    eventSource.value.close();
    eventSource.value = null;
  }

  if (window.electronAPI && window.electronAPI.connectFeishuSSE) {
    try {
      await window.electronAPI.connectFeishuSSE();
      feishuConnected.value = true;

      window.electronAPI.onFeishuEvent((data) => {
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
      handleFeishuEvent(data);
    } catch (e) {
      console.error("解析飞书事件失败:", e);
    }
  };

  es.onerror = () => {
    feishuConnected.value = false;
  };

  es.onopen = () => {
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

    if (!showDialog.value) {
      showDialog.value = true;
    }

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
    formData.append('audio', audioBlob, 'recording.webm');
    formData.append('channel', 'feishu');

    const response = await axios.post(
      `${API_URL}/audio/upload`,
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 600000,
      }
    );

    if (response.data?.response) {
      messages.value.push({
        role: "assistant",
        content: response.data.response,
      });
      await nextTick();
      scrollToBottom();
    } else {
      messages.value.push({
        role: "ai",
        content: "语音识别失败: " + (response.data?.error || "无法识别语音内容"),
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

onMounted(() => {
  connectFeishuSSE();
  setTimeout(initLive2D, 500);
  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
  setClickThrough(true);
});

onUnmounted(() => {
  disconnectFeishuSSE();
  cleanupLive2D();
  window.removeEventListener('mousemove', onMouseMove);
  window.removeEventListener('mouseup', onMouseUp);
});
</script>

<style scoped>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

.desktop-pet-wrapper {
  width: 100vw;
  height: 100vh;
  background: transparent;
  overflow: hidden;
  position: relative;
}

.pet-container {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
  z-index: 1000;
  user-select: none;
  -webkit-user-select: none;
}

.dialog-bubble {
  position: absolute;
  right: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-right: 20px;
  width: 340px;
  max-height: 420px;
  background: rgba(255, 255, 255, 0.95);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15), 0 2px 8px rgba(0, 0, 0, 0.08);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.6);
}

.bubble-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.bubble-title {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
}

.bubble-close {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  color: white;
  width: 22px;
  height: 22px;
  border-radius: 50%;
  cursor: pointer;
  font-size: 11px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
}

.bubble-close:hover {
  background: rgba(255, 255, 255, 0.35);
}

.bubble-messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px 12px;
  max-height: 280px;
  min-height: 60px;
  scroll-behavior: smooth;
}

.bubble-messages::-webkit-scrollbar {
  width: 4px;
}

.bubble-messages::-webkit-scrollbar-track {
  background: transparent;
}

.bubble-messages::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 2px;
}

.bubble-message {
  margin-bottom: 8px;
  max-width: 88%;
  animation: msgSlideIn 0.25s ease-out;
}

@keyframes msgSlideIn {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.bubble-user {
  margin-left: auto;
}

.bubble-ai {
  margin-right: auto;
}

.bubble-message-content {
  display: inline-block;
  padding: 8px 12px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.5;
  word-wrap: break-word;
  text-align: left;
}

.bubble-user .bubble-message-content {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  border-bottom-right-radius: 4px;
}

.bubble-ai .bubble-message-content {
  background: #f0f2f5;
  color: #333;
  border-bottom-left-radius: 4px;
}

.tool-call-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #666;
}

.tool-icon {
  font-size: 13px;
}

.tool-text {
  font-family: monospace;
  background: #f5f5f5;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 11px;
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
}

.thinking-dots {
  font-style: italic;
  color: #999;
  font-size: 12px;
}

.audio-message,
.tts-message {
  display: flex;
  align-items: center;
  gap: 6px;
}

.audio-icon,
.tts-icon {
  font-size: 14px;
}

.audio-player {
  max-width: 160px;
  height: 28px;
}

.bubble-input {
  display: flex;
  gap: 6px;
  padding: 10px 12px;
  border-top: 1px solid rgba(0, 0, 0, 0.06);
  background: rgba(255, 255, 255, 0.5);
}

.bubble-input-field {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  border-radius: 20px;
  font-size: 13px;
  outline: none;
  background: white;
  transition: border-color 0.2s;
}

.bubble-input-field:focus {
  border-color: #667eea;
}

.bubble-input-field:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.bubble-send-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
  font-size: 15px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: opacity 0.2s, transform 0.1s;
  flex-shrink: 0;
}

.bubble-send-btn:hover:not(:disabled) {
  opacity: 0.85;
}

.bubble-send-btn:active:not(:disabled) {
  transform: scale(0.92);
}

.bubble-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.bubble-record-btn {
  width: 34px;
  height: 34px;
  border-radius: 50%;
  border: none;
  background: #f0f2f5;
  cursor: pointer;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.2s;
  flex-shrink: 0;
}

.bubble-record-btn:hover:not(:disabled) {
  background: #e4e6eb;
}

.bubble-record-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.bubble-record-btn.recording {
  background: #ff4757;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

.bubble-arrow {
  position: absolute;
  right: -8px;
  top: 50%;
  transform: translateY(-50%);
  width: 0;
  height: 0;
  border-top: 8px solid transparent;
  border-bottom: 8px solid transparent;
  border-left: 8px solid rgba(255, 255, 255, 0.95);
  border-right: none;
}

.bubble-fade-enter-active {
  animation: bubbleIn 0.3s ease-out;
}

.bubble-fade-leave-active {
  animation: bubbleOut 0.2s ease-in;
}

@keyframes bubbleIn {
  from {
    opacity: 0;
    transform: translateX(-10px) translateY(-50%) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateX(0) translateY(-50%) scale(1);
  }
}

@keyframes bubbleOut {
  from {
    opacity: 1;
    transform: translateX(0) translateY(-50%) scale(1);
  }
  to {
    opacity: 0;
    transform: translateX(-10px) translateY(-50%) scale(0.95);
  }
}

.live2d-wrapper {
  width: 300px;
  height: 400px;
  cursor: grab;
  position: relative;
}

.live2d-wrapper:active {
  cursor: grabbing;
}

#live2d-canvas {
  width: 100%;
  height: 100%;
  display: block;
}

.live2d-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  color: #999;
  font-size: 13px;
  background: rgba(255, 255, 255, 0.85);
  padding: 8px 16px;
  border-radius: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.toggle-dialog-btn {
  position: absolute;
  bottom: 10px;
  right: -10px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 3px 12px rgba(0, 0, 0, 0.15);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.25s ease;
  z-index: 10;
}

.toggle-dialog-btn:hover {
  transform: scale(1.1);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
}

.toggle-dialog-btn.active {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}

.toggle-dialog-btn.active .btn-icon {
  filter: brightness(10);
}

.btn-icon {
  font-size: 18px;
  line-height: 1;
}

.markdown-body {
  font-size: 13px;
  line-height: 1.6;
  word-wrap: break-word;
  overflow-wrap: break-word;
}

.markdown-body :deep(p) {
  margin: 0 0 8px 0;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 12px 0 6px 0;
  font-weight: 600;
  line-height: 1.3;
}

.markdown-body :deep(h1) { font-size: 16px; }
.markdown-body :deep(h2) { font-size: 15px; }
.markdown-body :deep(h3) { font-size: 14px; }

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: 4px 0;
  padding-left: 18px;
}

.markdown-body :deep(li) {
  margin: 2px 0;
}

.markdown-body :deep(code) {
  background: #f0f2f5;
  padding: 1px 5px;
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  color: #e83e8c;
}

.markdown-body :deep(pre) {
  background: #282c34;
  color: #abb2bf;
  padding: 10px 12px;
  border-radius: 8px;
  margin: 8px 0;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.45;
}

.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: inherit;
  font-size: inherit;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid #667eea;
  padding: 4px 10px;
  margin: 6px 0;
  color: #666;
  background: rgba(102, 126, 234, 0.05);
  border-radius: 0 6px 6px 0;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: 8px 0;
  font-size: 12px;
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid #e0e0e0;
  padding: 5px 8px;
  text-align: left;
}

.markdown-body :deep(th) {
  background: #f5f5f5;
  font-weight: 600;
}

.markdown-body :deep(a) {
  color: #667eea;
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid #e0e0e0;
  margin: 10px 0;
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: 6px;
  margin: 4px 0;
}

.markdown-body :deep(strong) {
  font-weight: 600;
  color: #333;
}

.markdown-body :deep(em) {
  font-style: italic;
}
</style>
