import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  // index.css is read raw by theme-contrast.tester.test.ts; vitest would otherwise blank CSS modules.
  test: { environment: 'jsdom', css: { include: [/index\.css/] } },
})
