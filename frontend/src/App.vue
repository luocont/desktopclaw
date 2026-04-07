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
          class="dialog-bubble glass-card"
          ref="dialogBubble"
        >
          <div class="bubble-header">
            <span class="bubble-title">DesktopClaw</span>
            <button class="bubble-close" @click="showDialog = false" aria-label="关闭对话框">
              <X :size="14" />
            </button>
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
                    <Wrench :size="14" class="tool-icon" />
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
                    <Mic :size="16" class="audio-icon" />
                    <audio controls class="audio-player">
                      <source :src="msg.audioPath" type="audio/ogg; codecs=opus">
                    </audio>
                  </div>
                </template>
                <template v-else-if="msg.ttsAudioPath">
                  <div class="tts-message">
                    <Volume2 :size="16" class="tts-icon" />
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
              aria-label="发送消息"
            >
              <Send :size="16" v-if="!loading" />
              <span v-else class="loading-dots">...</span>
            </button>
            <button
              @mousedown="startRecording"
              @mouseup="stopRecording"
              @mouseleave="stopRecording"
              @touchstart.prevent="startRecording"
              @touchend.prevent="stopRecording"
              :disabled="loading"
              :class="['bubble-record-btn', { recording: isRecording }]"
              :aria-label="isRecording ? '停止录音' : '开始录音'"
            >
              <Mic :size="16" />
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
        <div v-if="!isModelLoaded" class="live2d-loading">
          {{ modelError || '加载中...' }}
        </div>
      </div>

      <div class="button-row">
        <button
          class="toggle-dialog-btn"
          @click.stop="showModelPicker = false; showDialog = !showDialog"
          :class="{ active: showDialog }"
          title="打开对话框"
          :aria-label="showDialog ? '关闭对话框' : '打开对话框'"
        >
          <MessageCircle :size="20" />
        </button>
        <button
          class="model-switch-btn"
          @click.stop="showDialog = false; showModelPicker = !showModelPicker"
          :class="{ active: showModelPicker }"
          title="更换皮肤"
          :aria-label="showModelPicker ? '关闭皮肤选择' : '打开皮肤选择'"
        >
          <Palette :size="20" />
        </button>
      </div>

      <transition name="picker-fade">
        <div v-if="showModelPicker" class="model-picker glass-card" @click.stop>
          <div class="picker-header">
            <span>选择皮肤</span>
            <button class="picker-close" @click="showModelPicker = false" aria-label="关闭皮肤选择">
              <X :size="14" />
            </button>
          </div>
          <div class="picker-list">
            <div
              v-for="m in availableModels"
              :key="m.path"
              :class="['picker-item', { active: currentModelUrl === m.path }]"
              @click="switchModel(m.path)"
            >
              <Palette :size="16" class="picker-item-icon" />
              <span class="picker-item-name">{{ m.name }}</span>
              <Check v-if="currentModelUrl === m.path" :size="16" class="picker-check" />
            </div>
            <div v-if="availableModels.length === 0" class="picker-empty">
              暂无可用皮肤
            </div>
          </div>
        </div>
      </transition>
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
import {
  MessageCircle,
  X,
  Mic,
  Send,
  Palette,
  Check,
  Wrench,
  Volume2
} from 'lucide-vue-next';

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
const modelError = ref('');
let app = null;
let model = null;

const currentModelUrl = ref('/Haru/Haru.model3.json');
const availableModels = ref([]);
const showModelPicker = ref(false);

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

async function ensurePixiApp() {
  if (app) return;

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
}

async function loadModel() {
  try {
    modelError.value = '';
    await waitForCubismCore();
    await ensurePixiApp();

    window.PIXI = PIXI;

    model = await Live2DModel.from(currentModelUrl.value);

    updateModelScale();
    app.stage.addChild(model);

    isModelLoaded.value = true;

    playStartupAnimation();
    playIdleAnimation();
    setupModelInteraction();

  } catch (error) {
    console.error('Live2D 初始化失败:', error);
    modelError.value = error.message || '模型加载失败';
    isModelLoaded.value = false;
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

    const motionGroups = model.internalModel.motionManager.motionGroups;
    const expressionNames = model.internalModel.motionManager.expressionManager ? Object.keys(model.internalModel.motionManager.expressionManager.expressions || {}) : [];

    const firstGroup = Object.keys(motionGroups)[0];
    if (firstGroup && model.motion) {
      model.motion(firstGroup, 0, 3);
    }

    if (expressionNames.length > 0 && model.expression) {
      const randomExp = expressionNames[Math.floor(Math.random() * expressionNames.length)];
      setTimeout(() => { if (model && model.expression) model.expression(randomExp); }, 500);
      setTimeout(() => { if (model && model.expression) model.expression(expressionNames[0]); }, 2000);
    }
  } catch (error) {
    console.warn('播放启动动画失败:', error);
  }
}

let idleAnimationInterval = null;
function playIdleAnimation() {
  try {
    if (!model) return;

    const motionGroups = model.internalModel.motionManager.motionGroups;
    const expressionNames = model.internalModel.motionManager.expressionManager ? Object.keys(model.internalModel.motionManager.expressionManager.expressions || {}) : [];
    const groupNames = Object.keys(motionGroups);

    const playCurrentIdleAction = () => {
      if (!model) return;

      try {
        if (groupNames.length > 0 && model.motion) {
          const groupName = groupNames[Math.floor(Math.random() * groupNames.length)];
          const group = motionGroups[groupName];
          const index = Math.floor(Math.random() * (group?.length || 1));
          model.motion(groupName, index, 1);
        }

        if (expressionNames.length > 0 && model.expression) {
          const expName = expressionNames[Math.floor(Math.random() * expressionNames.length)];
          setTimeout(() => { if (model && model.expression) model.expression(expName); }, 500);
        }
      } catch (error) {
        console.warn('播放待机动作失败:', error);
      }
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

    const motionGroups = model.internalModel.motionManager.motionGroups;
    const expressionNames = model.internalModel.motionManager.expressionManager ? Object.keys(model.internalModel.motionManager.expressionManager.expressions || {}) : [];
    const groupNames = Object.keys(motionGroups);

    if (groupNames.length > 0 && model.motion) {
      const groupName = groupNames[Math.floor(Math.random() * groupNames.length)];
      const group = motionGroups[groupName];
      const index = Math.floor(Math.random() * (group?.length || 1));
      model.motion(groupName, index, 3);

      if (expressionNames.length > 0 && model.expression) {
        const randomExp = expressionNames[Math.floor(Math.random() * expressionNames.length)];
        setTimeout(() => { if (model && model.expression) model.expression(randomExp); }, 300);
        setTimeout(() => { if (model && model.expression) model.expression(expressionNames[0]); }, 2500);
      }
    }
  } catch (error) {
    console.warn('播放交互动画失败:', error);
  }
}

function cleanupModel() {
  if (idleAnimationInterval) {
    clearInterval(idleAnimationInterval);
    idleAnimationInterval = null;
  }

  if (model) {
    if (app && app.stage) {
      app.stage.removeChild(model);
    }
    model.destroy();
    model = null;
  }

  isModelLoaded.value = false;
  modelError.value = '';
}

function cleanupLive2D() {
  cleanupModel();

  if (app) {
    app.destroy(true, { children: true, texture: true, baseTexture: true });
    app = null;
  }
}

async function scanModels() {
  if (window.electronAPI && window.electronAPI.scanLive2DModels) {
    try {
      const result = await window.electronAPI.scanLive2DModels();
      if (result.success && result.models.length > 0) {
        availableModels.value = result.models;
      }
    } catch (error) {
      console.error('扫描模型失败:', error);
    }
  } else {
    availableModels.value = [{ name: 'Haru', path: '/Haru/Haru.model3.json' }];
  }
}

async function switchModel(modelPath) {
  currentModelUrl.value = modelPath;
  showModelPicker.value = false;
  cleanupModel();
  await loadModel();
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
  setTimeout(loadModel, 500);
  window.addEventListener('mousemove', onMouseMove);
  window.addEventListener('mouseup', onMouseUp);
  setClickThrough(true);
  scanModels();
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
  gap: var(--space-sm);
  z-index: var(--z-modal);
  user-select: none;
  -webkit-user-select: none;
}

/* ===== 对话框气泡 - Glassmorphism + Indigo ===== */
.dialog-bubble {
  position: absolute;
  right: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-right: 20px;
  width: 340px;
  max-height: 420px;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.bubble-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-lg);
  background: var(--accent-indigo);
  border-bottom: 1px solid var(--glass-border);
}

.bubble-title {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--text-primary);
  letter-spacing: 0.5px;
}

.bubble-close {
  background: rgba(255, 255, 255, 0.15);
  border: none;
  color: var(--text-primary);
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast);
}

.bubble-close:hover {
  background: rgba(255, 255, 255, 0.25);
}

.bubble-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md);
  max-height: 280px;
  min-height: 60px;
  scroll-behavior: smooth;
  background: var(--bg-secondary);
}

.bubble-messages::-webkit-scrollbar {
  width: 4px;
}

.bubble-messages::-webkit-scrollbar-track {
  background: transparent;
}

.bubble-messages::-webkit-scrollbar-thumb {
  background: var(--glass-border);
  border-radius: var(--radius-sm);
}

.bubble-message {
  margin-bottom: var(--space-sm);
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
  padding: 10px var(--space-md);
  border-radius: var(--radius-md);
  font-size: var(--font-size-base);
  line-height: 1.5;
  word-wrap: break-word;
  text-align: left;
}

.bubble-user .bubble-message-content {
  background: var(--accent-indigo);
  color: var(--text-primary);
  border-bottom-right-radius: var(--radius-sm);
}

.bubble-ai .bubble-message-content {
  background: var(--glass-bg-strong);
  color: var(--text-secondary);
  border: 1px solid var(--glass-border);
  border-bottom-left-radius: var(--radius-sm);
}

.tool-call-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--font-size-sm);
  color: var(--text-muted);
}

.tool-icon {
  color: var(--text-muted);
}

.tool-text {
  font-family: monospace;
  background: var(--glass-bg-strong);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: var(--font-size-xs);
}

.thinking-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
}

.thinking-dots {
  font-style: italic;
  color: var(--text-muted);
  font-size: var(--font-size-sm);
}

.audio-message,
.tts-message {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}

.audio-icon,
.tts-icon {
  color: var(--text-muted);
}

.audio-player {
  max-width: 160px;
  height: 28px;
}

.bubble-input {
  display: flex;
  gap: var(--space-sm);
  padding: var(--space-md);
  border-top: 1px solid var(--glass-border);
  background: var(--glass-bg);
}

.bubble-input-field {
  flex: 1;
  padding: 8px var(--space-md);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-full);
  font-size: var(--font-size-base);
  outline: none;
  background: var(--bg-tertiary);
  color: var(--text-primary);
  transition: border-color var(--transition-fast);
}

.bubble-input-field::placeholder {
  color: var(--text-subtle);
}

.bubble-input-field:focus {
  border-color: var(--accent-indigo-light);
}

.bubble-input-field:disabled {
  background: var(--bg-secondary);
  cursor: not-allowed;
  opacity: 0.6;
}

.bubble-send-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  border: none;
  background: var(--accent-indigo);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-fast);
  flex-shrink: 0;
  color: var(--text-primary);
}

.bubble-send-btn:hover:not(:disabled) {
  background: var(--accent-indigo-light);
  transform: scale(1.05);
}

.bubble-send-btn:active:not(:disabled) {
  transform: scale(0.95);
}

.bubble-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.loading-dots {
  color: var(--text-primary);
  font-size: var(--font-size-base);
}

.bubble-record-btn {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-full);
  border: none;
  background: var(--glass-bg-strong);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast);
  flex-shrink: 0;
  color: var(--text-secondary);
  border: 1px solid var(--glass-border);
}

.bubble-record-btn:hover:not(:disabled) {
  background: var(--glass-bg);
}

.bubble-record-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.bubble-record-btn.recording {
  background: var(--error);
  color: var(--text-primary);
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.7; }
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
  border-left: 8px solid var(--glass-bg);
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

/* ===== Live2D ===== */
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
  color: var(--text-secondary);
  font-size: var(--font-size-base);
  background: var(--glass-bg-strong);
  padding: var(--space-sm) var(--space-md);
  border-radius: var(--radius-full);
  border: 1px solid var(--glass-border);
}

/* ===== 按钮行 ===== */
.button-row {
  position: absolute;
  left: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-left: 10px;
  display: flex;
  flex-direction: column;
  gap: var(--space-sm);
}

.toggle-dialog-btn,
.model-switch-btn {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  border: none;
  background: var(--glass-bg-strong);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--transition-normal);
  z-index: var(--z-base);
  color: var(--text-secondary);
  border: 1px solid var(--glass-border);
}

.toggle-dialog-btn:hover,
.model-switch-btn:hover {
  transform: scale(1.1);
  background: var(--glass-bg);
}

.toggle-dialog-btn.active {
  background: var(--accent-indigo);
  color: var(--text-primary);
}

.model-switch-btn.active {
  background: var(--accent-amber);
  color: var(--text-primary);
}

/* ===== Markdown 样式 ===== */
.markdown-body {
  font-size: var(--font-size-base);
  line-height: 1.6;
  word-wrap: break-word;
  overflow-wrap: break-word;
  color: var(--text-secondary);
}

.markdown-body :deep(p) {
  margin: 0 0 var(--space-sm) 0;
}

.markdown-body :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: var(--space-md) 0 var(--space-sm) 0;
  font-weight: 600;
  line-height: 1.3;
  color: var(--text-primary);
}

.markdown-body :deep(h1) { font-size: var(--font-size-lg); }
.markdown-body :deep(h2) { font-size: var(--font-size-md); }
.markdown-body :deep(h3) { font-size: var(--font-size-base); }

.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  margin: var(--space-sm) 0;
  padding-left: 20px;
}

.markdown-body :deep(li) {
  margin: 2px 0;
}

.markdown-body :deep(code) {
  background: var(--glass-bg-strong);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: var(--font-size-sm);
  color: var(--accent-indigo-light);
}

.markdown-body :deep(pre) {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  padding: var(--space-md);
  border-radius: var(--radius-md);
  margin: var(--space-sm) 0;
  overflow-x: auto;
  font-size: var(--font-size-sm);
  line-height: 1.5;
  border: 1px solid var(--glass-border);
}

.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
  color: inherit;
  font-size: inherit;
}

.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--accent-indigo);
  padding: var(--space-sm) var(--space-md);
  margin: var(--space-sm) 0;
  color: var(--text-muted);
  background: var(--glass-bg);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
}

.markdown-body :deep(table) {
  width: 100%;
  border-collapse: collapse;
  margin: var(--space-sm) 0;
  font-size: var(--font-size-sm);
}

.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--glass-border);
  padding: var(--space-sm);
  text-align: left;
}

.markdown-body :deep(th) {
  background: var(--glass-bg-strong);
  font-weight: 600;
  color: var(--text-primary);
}

.markdown-body :deep(a) {
  color: var(--accent-indigo-light);
  text-decoration: none;
}

.markdown-body :deep(a:hover) {
  text-decoration: underline;
}

.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--glass-border);
  margin: var(--space-md) 0;
}

.markdown-body :deep(img) {
  max-width: 100%;
  border-radius: var(--radius-sm);
  margin: var(--space-sm) 0;
}

.markdown-body :deep(strong) {
  font-weight: 600;
  color: var(--text-primary);
}

/* ===== 皮肤选择器 - Glassmorphism + Amber ===== */
.model-picker {
  position: absolute;
  right: 100%;
  top: 50%;
  transform: translateY(-50%);
  margin-right: 20px;
  width: 220px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  z-index: calc(var(--z-modal) + 1);
}

.picker-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-lg);
  background: var(--accent-amber);
  border-bottom: 1px solid var(--glass-border);
}

.picker-header span {
  font-size: var(--font-size-base);
  font-weight: 600;
  color: var(--text-primary);
}

.picker-close {
  background: rgba(255, 255, 255, 0.15);
  border: none;
  color: var(--text-primary);
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition-fast);
}

.picker-close:hover {
  background: rgba(255, 255, 255, 0.25);
}

.picker-list {
  padding: var(--space-sm);
  max-height: 240px;
  overflow-y: auto;
  background: var(--bg-secondary);
}

.picker-list::-webkit-scrollbar {
  width: 4px;
}

.picker-list::-webkit-scrollbar-track {
  background: transparent;
}

.picker-list::-webkit-scrollbar-thumb {
  background: var(--glass-border);
  border-radius: var(--radius-sm);
}

.picker-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 10px var(--space-md);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-fast);
  margin-bottom: 2px;
}

.picker-item:last-child {
  margin-bottom: 0;
}

.picker-item:hover {
  background: var(--glass-bg-strong);
}

.picker-item.active {
  background: rgba(217, 119, 6, 0.15);
  border: 1px solid rgba(217, 119, 6, 0.3);
}

.picker-item-icon {
  flex-shrink: 0;
  color: var(--text-muted);
}

.picker-item.active .picker-item-icon {
  color: var(--accent-amber);
}

.picker-item-name {
  flex: 1;
  font-size: var(--font-size-base);
  color: var(--text-secondary);
  font-weight: 500;
}

.picker-item.active .picker-item-name {
  color: var(--accent-amber);
  font-weight: 600;
}

.picker-check {
  color: var(--accent-amber);
  flex-shrink: 0;
}

.picker-empty {
  text-align: center;
  padding: var(--space-xl) var(--space-md);
  color: var(--text-muted);
  font-size: var(--font-size-base);
}

.picker-fade-enter-active {
  animation: pickerIn 0.25s ease-out;
}

.picker-fade-leave-active {
  animation: pickerOut 0.15s ease-in;
}

@keyframes pickerIn {
  from {
    opacity: 0;
    transform: translateX(-10px) translateY(-50%) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translateX(0) translateY(-50%) scale(1);
  }
}

@keyframes pickerOut {
  from {
    opacity: 1;
    transform: translateX(0) translateY(-50%) scale(1);
  }
  to {
    opacity: 0;
    transform: translateX(-10px) translateY(-50%) scale(0.95);
  }
}
</style>
