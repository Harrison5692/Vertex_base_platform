import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // Inside Docker Compose, containers reach each other by service name
  // ("backend"), not localhost — localhost inside a container means
  // that container itself. Override via VITE_BACKEND_TARGET if running
  // outside Docker.
  const backendTarget = env.VITE_BACKEND_TARGET || 'http://localhost:8000'

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
          // backend routes have no /api prefix — strip it before forwarding
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  }
})
