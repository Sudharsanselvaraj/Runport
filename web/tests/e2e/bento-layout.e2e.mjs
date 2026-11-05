// Playwright layout test for the landing page bento section ("What Runport does").
//
// At 1440, 1280, 1024, 768 and 390 px it loads the built page, scrolls to the
// section and asserts, inside every card:
//   (a) no two visible text elements overlap,
//   (b) nothing is clipped: text containers do not overflow (scrollWidth <=
//       clientWidth) and stay inside their card; the ring value fits inside the ring,
//   (c) cards in the same grid row share a top edge (within 1 px),
//   (d) the page has no horizontal scroll,
//   (e) text contrast is at least 4.5:1 (axe color-contrast) in the section.
// It checks the animated page at two moments and the reduced-motion page.
//
// Not part of `npm test` because it needs a browser. Run it against a served
// build (e.g. `npm run build:site && npx vite preview --config vite.landing.config.ts --port 4174`):
//
//   RUNPORT_E2E_MODULES=/path/to/dir/with/node_modules \
//   CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
//   node tests/e2e/bento-layout.e2e.mjs [url]
//
// E2E_SELFCHECK=1 injects broken CSS (a shifted card, overlapping text, an
// oversized ring label) and passes only if every one of those is caught.
//
// It needs playwright-core and axe-core; RUNPORT_E2E_MODULES points at a folder
// whose node_modules has them (they are not dependencies of this package).
import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'

const base = process.env.RUNPORT_E2E_MODULES ? path.join(process.env.RUNPORT_E2E_MODULES, 'package.json') : import.meta.url
const require = createRequire(base)
const { chromium } = require('playwright-core')
const AXE = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8')

const URL = process.argv[2] || 'http://127.0.0.1:4174/'
const WIDTHS = [1440, 1280, 1024, 768, 390]
const ROWS = (w) => (w >= 1200 ? [['targets', 'plan'], ['spend', 'results']] : w >= 768 ? [['targets', 'plan']] : [])

function inPage() {
  const cards = [...document.querySelectorAll('#features .rp-bento-cell')]
  const visible = (el, card) => {
    for (let n = el; n && n !== card.parentElement; n = n.parentElement) {
      const cs = getComputedStyle(n)
      if (cs.display === 'none' || cs.visibility === 'hidden' || Number(cs.opacity) < 0.05) return false
    }
    const r = el.getBoundingClientRect()
    return r.width > 1 && r.height > 1
  }
  const ownText = (el) => [...el.childNodes].some((c) => c.nodeType === 3 && c.textContent.trim())
  const problems = []
  const tops = {}
  for (const cell of cards) {
    const name = cell.className.match(/is-(\w+)/)?.[1]
    const card = cell.querySelector('.rp-bento-card')
    const cr = card.getBoundingClientRect()
    tops[name] = cr.top
    const texts = [...card.querySelectorAll('*')].filter((el) => ownText(el) && visible(el, card) && !el.closest('.rp-sr-only'))
    // (b) inside the card, no overflow
    for (const el of texts) {
      const r = el.getBoundingClientRect()
      if (r.left < cr.left - 1 || r.right > cr.right + 1 || r.top < cr.top - 1 || r.bottom > cr.bottom + 1) problems.push(`${name}: "${el.textContent.trim().slice(0, 40)}" sticks out of the card`)
      const cs = getComputedStyle(el)
      if (cs.display !== 'inline' && el.clientWidth > 0 && el.scrollWidth > el.clientWidth + 1) problems.push(`${name}: "${el.textContent.trim().slice(0, 40)}" overflows its box (${el.scrollWidth} > ${el.clientWidth})`)
    }
    // (a) no overlapping text
    for (let i = 0; i < texts.length; i++) {
      for (let j = i + 1; j < texts.length; j++) {
        const a = texts[i]
        const b = texts[j]
        if (a.contains(b) || b.contains(a)) continue
        const ra = a.getBoundingClientRect()
        const rb = b.getBoundingClientRect()
        const w = Math.min(ra.right, rb.right) - Math.max(ra.left, rb.left)
        const h = Math.min(ra.bottom, rb.bottom) - Math.max(ra.top, rb.top)
        if (w > 1 && h > 1) problems.push(`${name}: "${a.textContent.trim().slice(0, 30)}" overlaps "${b.textContent.trim().slice(0, 30)}"`)
      }
    }
  }
  // ring text fits inside the ring's inner circle
  const ring = document.querySelector('#features .rp-g-ring')
  if (ring) {
    const rr = ring.getBoundingClientRect()
    const cx = rr.left + rr.width / 2
    const cy = rr.top + rr.height / 2
    const inner = ((66 - 3) / 150) * rr.width
    for (const el of ring.querySelectorAll('.rp-g-ring-label strong, .rp-g-ring-label span')) {
      const r = el.getBoundingClientRect()
      for (const [x, y] of [[r.left, r.top], [r.right, r.top], [r.left, r.bottom], [r.right, r.bottom]]) {
        if (Math.hypot(x - cx, y - cy) > inner + 0.5) {
          problems.push(`spend: ring text "${el.textContent.trim()}" leaves the ring`)
          break
        }
      }
    }
  }
  return { problems, tops, scrollW: document.documentElement.scrollWidth, innerW: innerWidth }
}

async function check(page, w, label) {
  const r = await page.evaluate(inPage)
  const fails = [...r.problems]
  for (const row of ROWS(w)) {
    const ts = row.map((n) => r.tops[n])
    if (Math.max(...ts) - Math.min(...ts) > 1) fails.push(`row ${row.join(' + ')}: top edges differ (${ts.map((t) => t.toFixed(1)).join(' vs ')})`)
  }
  if (r.scrollW > r.innerW) fails.push(`horizontal scroll: ${r.scrollW} > ${r.innerW}`)
  return fails.map((f) => `[${w} ${label}] ${f}`)
}

const BROKEN = `
  #features .rp-bento-cell.is-plan .rp-bento-card { margin-top: 12px; }
  #features .rp-bento-cell.is-targets .rp-bento-text p { margin-top: -30px; }
  #features .rp-g-ring-label strong { font-size: 60px; }
`
if (process.env.E2E_SELFCHECK) {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' })
  await page.goto(URL, { waitUntil: 'networkidle' })
  for (let y = 0; y < 30000 && !(await page.locator('#features').count()); y += 600) await page.evaluate((v) => window.scrollTo(0, v), y)
  await page.locator('#features').scrollIntoViewIfNeeded()
  await page.waitForTimeout(1000)
  await page.addStyleTag({ content: BROKEN })
  await page.waitForTimeout(400) // let the page restyle before measuring
  const fails = await check(page, 1440, 'selfcheck')
  await browser.close()
  const caught = ['top edges differ', 'overlaps', 'leaves the ring'].map((k) => fails.some((f) => f.includes(k)))
  console.log(JSON.stringify({ caught: { misaligned: caught[0], overlap: caught[1], ringText: caught[2] } }))
  process.exit(caught.every(Boolean) ? 0 : 1)
}

const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' })
const results = {}
let failures = []
for (const w of WIDTHS) {
  const out = []
  for (const reducedMotion of ['no-preference', 'reduce']) {
    const ctx = await browser.newContext({ viewport: { width: w, height: 900 }, reducedMotion, isMobile: w < 768, hasTouch: w < 768 })
    const page = await ctx.newPage()
    await page.goto(URL, { waitUntil: 'networkidle' })
    for (let y = 0; y < 30000 && !(await page.locator('#features').count()); y += 600) {
      await page.evaluate((v) => window.scrollTo(0, v), y)
      await page.waitForTimeout(50)
    }
    await page.locator('#features').scrollIntoViewIfNeeded()
    await page.waitForTimeout(1300)
    if (reducedMotion === 'reduce') {
      out.push(...(await check(page, w, 'reduced motion')))
    } else {
      out.push(...(await check(page, w, 't≈1s')))
      await page.waitForTimeout(4500) // plan card mid-change, spend ring part-filled
      out.push(...(await check(page, w, 't≈6s')))
      await page.waitForTimeout(3500) // spend guard blocked, plan rejected
      out.push(...(await check(page, w, 't≈9s')))
      await page.addScriptTag({ content: AXE })
      const axe = await page.evaluate(async () => {
        const res = await window.axe.run('#features', { runOnly: ['color-contrast'] })
        return res.violations.flatMap((v) => v.nodes.map((n) => `${n.target.join(' ')} (${n.any[0]?.data?.contrastRatio})`))
      })
      out.push(...axe.map((a) => `[${w}] contrast below 4.5:1: ${a}`))
    }
    await ctx.close()
  }
  results[w] = out.length ? out : 'pass'
  failures = failures.concat(out)
}
await browser.close()
console.log(JSON.stringify(results, null, 1))
process.exit(failures.length ? 1 : 0)
