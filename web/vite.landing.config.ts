import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

// Public landing site: built separately from the local Workbench so the hosted
// site ships no dashboard code and makes no /api calls.
//
// LANDING_BASE sets the path the site is served from (GitHub Pages serves this
// repository at /Runport/). Source files reference public assets and the docs
// from the root ("/assets/landing/...", "/docs/"); this plugin prefixes those
// with the base at build time. With the default base "/" nothing changes.
const BASE = process.env.LANDING_BASE || '/'

function rebaseRootPaths(base: string): Plugin {
  return {
    name: 'runport-rebase-root-paths',
    enforce: 'pre',
    transform(code, id) {
      if (base === '/' || id.includes('node_modules') || !/\.(tsx?|css)$/.test(id)) return null
      const out = code.replace(/(["'`(])\/(assets\/landing\/|docs\/)/g, `$1${base}$2`)
      return out === code ? null : { code: out, map: null }
    },
  }
}

export default defineConfig({
  root: 'landing',
  base: BASE,
  publicDir: 'public',
  plugins: [rebaseRootPaths(BASE), react()],
  // /docs/ is the documentation portal: proxied to its dev server here, bundled by `npm run build:site`.
  server: { port: 5174, proxy: { '/docs': { target: 'http://127.0.0.1:5175', ws: true } } },
  preview: { port: 4174 },
  build: {
    outDir: '../dist-landing',
    emptyOutDir: true,
  },
})
