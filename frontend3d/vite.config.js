import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies API and FastAPI-owned visual assets to the same origin.
export default defineConfig({
  base: '/static/frontend3d/',
  plugins: [react()],
  build: {
    // 產物由唯一 FastAPI 的 /static 掛載；使用者只需開啟 8002。
    outDir: '../roompilot/server/static/frontend3d',
    emptyOutDir: true,
  },
  server: {
    proxy: {
      '/api': 'http://localhost:8002',
      '/static': 'http://localhost:8002',
    },
  },
})
