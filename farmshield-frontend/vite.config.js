import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    open: true,
  },
  define: {
    'import.meta.env.VITE_API_URL': JSON.stringify(process.env.VITE_API_URL || ''),
    'import.meta.env.VITE_API_KEY': JSON.stringify(process.env.VITE_API_KEY || ''),
    'import.meta.env.VITE_DEMO_MODE': JSON.stringify(process.env.VITE_DEMO_MODE || 'false'),
  },
})
