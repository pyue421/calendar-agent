import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: './src/test/setup.js',
    exclude: ['**/node_modules/**', '**/dist/**', '**/scenario-card-model.test.js'],
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
})
