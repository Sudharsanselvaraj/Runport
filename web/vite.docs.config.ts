import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Documentation portal: a static site built on its own. It never imports the
// Workbench or the landing page and never calls the local Runport API.
// base './' + hash routes let the build be served from any host or sub-path.
export default defineConfig({
  root: 'docs',
  base: './',
  publicDir: 'public',
  plugins: [react()],
  server: { port: 5175 },
  preview: { port: 4175 },
  build: {
    outDir: '../dist-docs',
    emptyOutDir: true,
  },
})
