import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Public landing site: built separately from the local Workbench so the hosted
// site ships no dashboard code and makes no /api calls.
export default defineConfig({
  root: 'landing',
  publicDir: 'public',
  plugins: [react()],
  server: { port: 5174 },
  preview: { port: 4174 },
  build: {
    outDir: '../dist-landing',
    emptyOutDir: true,
  },
})
