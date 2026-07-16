import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/count': { target: 'http://127.0.0.1:5050', rewrite: path => path.replace(/^\/api\/count/, '') },
      '/api/db':    { target: 'http://127.0.0.1:5051', rewrite: path => path.replace(/^\/api\/db/,    '') },
    },
  },
})
