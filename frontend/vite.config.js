import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/chat':         'http://localhost:8000',
      '/feedback':     'http://localhost:8000',
      '/health':       'http://localhost:8000',
      '/demo-members': 'http://localhost:8000',
      '/voice':        'http://localhost:8000',
      '/dashboard':    'http://localhost:8000',
    }
  }
})
