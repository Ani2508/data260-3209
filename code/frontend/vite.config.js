import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': 'http://localhost:8509' }, // FastAPI backend (PORT_BASE)
    fs: { allow: ['..'] },                      // lets us reuse web_application/styles.css
  },
})