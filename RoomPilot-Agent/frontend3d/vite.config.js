import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies /api to the FastAPI backend, so the frontend talks to a
// same-origin path and no CORS handling is needed in the browser.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': 'http://localhost:8002' } },
})
