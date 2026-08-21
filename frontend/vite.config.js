import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev server proxies API and FastAPI-owned visual assets to the same origin.
export default defineConfig({
  base: '/static/frontend3d/',
  plugins: [react()],
  build: {
    // 產物由唯一 FastAPI 的 /static 掛載；使用者只需開啟 8002。
    outDir: '../backend/server/static/frontend3d',
    emptyOutDir: true,
  },
  server: {
    // 容器裡 FastAPI 不在 localhost，而在 compose 的 `web` 服務；本機開發不設
    // 這個變數，行為與先前完全相同。
    proxy: (() => {
      const target = process.env.VITE_API_TARGET || 'http://localhost:8002'
      return {
        '/api': target,
        // `/static` 原本整段轉給 FastAPI，但本專案的 base 就是
        // `/static/frontend3d/`——等於把 dev server 自己的位址（含 /@vite/client
        // 與 HMR 用戶端）也一起轉走，dev server 因此完全連不到，畫面永遠是
        // FastAPI 上那份**已建置**的舊產物。改成排除 base：^ 開頭的 key 會被
        // Vite 當成 RegExp（見 Vite server.proxy 文件）。
        // 其餘 /static/**（材質、GLB、surface assets）仍照舊轉給 FastAPI。
        '^/static/(?!frontend3d(/|$))': target,
      }
    })(),
    // 下面兩項只在容器裡開：0.0.0.0 才連得進來；Windows/WSL2 的 bind mount
    // 不會把 inotify 事件傳進容器，不輪詢就沒有 HMR。
    ...(process.env.VITE_IN_DOCKER
      ? { host: true, watch: { usePolling: true, interval: 300 } }
      : {}),
  },
})
