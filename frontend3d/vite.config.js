import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies API and FastAPI-owned visual assets to the same origin.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8002',
      '/static': 'http://localhost:8002',
    },
  },
})
