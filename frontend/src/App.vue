<template>
    <div style="padding: 20px;">
      <h2>Vue3 + Electron 输入框示例</h2>
      <!-- 输入框：绑定响应式变量 -->
      <input 
        v-model="inputValue" 
        placeholder="请输入要发送的内容" 
        style="width: 300px; padding: 8px; margin-right: 10px;"
      />
      <!-- 发送按钮：点击触发发送函数 -->
      <button 
        @click="sendToPort" 
        style="padding: 8px 16px; cursor: pointer;"
      >
        发送到 localhost:3000 端口
      </button>
  
      <!-- 显示发送结果 -->
      <div style="margin-top: 20px; color: #666;" v-if="result">
        {{ result }}
      </div>
    </div>
  </template>
  
  <script setup>
  import { ref } from 'vue'
  import axios from 'axios'
  
  // 1. 响应式变量：绑定输入框
  const inputValue = ref('')
  // 2. 响应式变量：存储发送结果
  const result = ref('')
  
  // 3. 核心函数：发送内容到指定端口
  const sendToPort = async () => {
    // 校验输入框非空
    if (!inputValue.value) {
      result.value = '❌ 请输入要发送的内容！'
      return
    }
  
    try {
      // 发送 POST 请求到 localhost:3000 端口
      const response = await axios.post('http://localhost:3000', {
        message: inputValue.value // 要发送的内容
      }, {
        headers: {
          'Content-Type': 'application/json' // 指定 JSON 格式
        }
      })
  
      // 发送成功：显示结果
      result.value = `✅ 发送成功！端口返回：${JSON.stringify(response.data)}`
      // 清空输入框
      inputValue.value = ''
    } catch (error) {
      // 发送失败：显示错误
      result.value = `❌ 发送失败：${error.message}（请确认 3000 端口服务已启动）`
    }
  }
  </script>