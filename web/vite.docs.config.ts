import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Documentation portal: a static site built on its own. It never imports the
// Workbench or the landing page and never calls the local Runport API.
// base './' + hash routes let the build be served from any host or sub-path.
// In development the portal is served under /docs/ so the landing dev server can proxy it.
export default defineConfig(({ command }) => ({
  root: 'docs',
  base: command === 'serve' ? '/docs/' : './',
  publicDir: 'public',
  plugins: [react()],
  server: { port: 5175 },
  preview: { port: 4175 },
  build: {
    outDir: '../dist-docs',
    emptyOutDir: true,
  },
}))
