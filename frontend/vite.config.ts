import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const proxyTarget = process.env.VITE_PROXY_TARGET ?? 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 5173,
    // Bind-mounted source on macOS/Windows Docker does not emit inotify events.
    watch: { usePolling: true, interval: 300 },
    proxy: {
      '/api': { target: proxyTarget, changeOrigin: true },
      '/admin': { target: proxyTarget, changeOrigin: true },
      '/static': { target: proxyTarget, changeOrigin: true },
      // Signature and docket photos are served by Django out of MEDIA_ROOT.
      '/media': { target: proxyTarget, changeOrigin: true },
    },
  },
})
