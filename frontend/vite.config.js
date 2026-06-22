import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import path from "path";

export default defineConfig({
  base: './',
  plugins: [vue()],
  server: {
    port: 5173,
    host: "0.0.0.0",
    headers: {
      "Content-Security-Policy":
        "default-src 'self'; connect-src 'self' blob: http://127.0.0.1:18790 http://localhost:18790; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; media-src 'self' blob: http://127.0.0.1:18790; img-src 'self' data: blob:;",
    },
  },
  resolve: {
    alias: {
      "@": path.join(__dirname, "src"),
    },
  },
  optimizeDeps: {
    include: ['pixi.js', 'pixi-live2d-display'],
  },
});
