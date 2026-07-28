
/*
Vite 构建配置 + 代理设置
Vite 代理：前端 localhost:5173 请求 /api/xxx → 
Vite 自动转发到 localhost:8000 。杜绝跨域问题，开发体验完美。
*/
import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import { resolve } from "path"

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/static": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
})