import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Public landing site: built separately from the local Workbench so the hosted
// site ships no dashboard code and makes no /api calls.
export default defineConfig({
  root: 'landing',
  publicDir: 'public',
  plugins: [react()],
  // /docs/ is the documentation portal: proxied to its dev server here, bundled by `npm run build:site`.
  server: { port: 5174, proxy: { '/docs': { target: 'http://127.0.0.1:5175', ws: true } } },
  preview: { port: 4174 },
  build: {
    outDir: '../dist-landing',
    emptyOutDir: true,
  },
})
