import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Dev server proxies every backend-originated prefix to the FastAPI service;
// production builds are served from FastAPI itself, so paths stay relative.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/demo': 'http://127.0.0.1:8000',
      '/results': 'http://127.0.0.1:8000',
      '/static': 'http://127.0.0.1:8000'
    }
  },
  build: {
    outDir: '../app/static/dist',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1600
  }
})
