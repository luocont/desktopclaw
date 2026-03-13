import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import electron from 'vite-plugin-electron'
import path from 'path'

export default defineConfig({
  plugins: [
    vue(),
    // 配置 electron 插件，指向主进程文件
    electron({
      entry: path.join(__dirname, 'electron/main.js')
    })
  ],
  server: {
    port: 5173, // 固定端口，和 electron/main.js 里的一致
    host: '0.0.0.0' // 允许外部访问（Electron 加载需要）
  },
  resolve: {
    alias: {
      '@': path.join(__dirname, 'src')
    }
  }
})