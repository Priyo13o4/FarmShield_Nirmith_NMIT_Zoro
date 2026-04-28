import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    open: true,
  },
  define: {
    'import.meta.env.VITE_API_URL': JSON.stringify('http://localhost:8000'),
    'import.meta.env.VITE_API_KEY': JSON.stringify(''),
    'import.meta.env.VITE_DEMO_MODE': JSON.stringify('false'),
  },
})
