import vue from "@vitejs/plugin-vue"
import { defineConfig } from "vite"

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://127.0.0.1:8080",
      "/livez": "http://127.0.0.1:8080",
      "/readyz": "http://127.0.0.1:8080",
      "/search": "http://127.0.0.1:8080",
    },
  },
})
