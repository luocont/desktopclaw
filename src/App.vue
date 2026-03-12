<template>
  <div class="app-container">
    <h1>DesktopClaw</h1>

    <div class="input-section">
      <label for="input-field">输入框</label>
      <input
        id="input-field"
        v-model="inputValue"
        type="text"
        placeholder="请输入内容..."
        @keyup.enter="handleSubmit"
      />
      <button @click="handleSubmit" :disabled="loading">
        {{ loading ? '提交中...' : '提交' }}
      </button>
    </div>

    <div v-if="response" class="response-section">
      <h3>后端响应:</h3>
      <pre>{{ JSON.stringify(response, null, 2) }}</pre>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const inputValue = ref('')
const response = ref(null)
const loading = ref(false)

/**
 * 提交输入框数据到后端
 * 路由: 'submit-input'
 */
const handleSubmit = async () => {
  if (!inputValue.value.trim()) {
    return
  }

  loading.value = true
  try {
    // 调用 Electron IPC 发送数据到后端
    // 路由: 'submit-input'
    const result = await window.electronAPI.submitInput(inputValue.value)
    response.value = result
    console.log('后端返回结果:', result)
  } catch (error) {
    console.error('提交失败:', error)
    response.value = {
      success: false,
      error: error.message
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.app-container {
  padding: 40px;
  max-width: 600px;
  margin: 0 auto;
}

h1 {
  text-align: center;
  margin-bottom: 40px;
  color: #333;
}

.input-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

label {
  font-weight: 600;
  color: #555;
}

input {
  padding: 12px 16px;
  font-size: 16px;
  border: 2px solid #ddd;
  border-radius: 8px;
  outline: none;
  transition: border-color 0.2s;
}

input:focus {
  border-color: #4a9eff;
}

button {
  padding: 12px 24px;
  font-size: 16px;
  font-weight: 600;
  color: white;
  background: #4a9eff;
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: background 0.2s;
}

button:hover:not(:disabled) {
  background: #3a8eef;
}

button:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.response-section {
  margin-top: 32px;
  padding: 20px;
  background: #f5f5f5;
  border-radius: 8px;
}

.response-section h3 {
  margin-top: 0;
  color: #333;
}

pre {
  white-space: pre-wrap;
  word-wrap: break-word;
  font-size: 14px;
  color: #444;
}
</style>
