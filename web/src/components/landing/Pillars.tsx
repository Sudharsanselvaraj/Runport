import React, { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useInView, useReducedMotion, type Variants } from 'framer-motion'
import {
  Activity,
  Eraser,
  Fingerprint,
  Gauge,
  GitCompare,
  type LucideIcon,
  NotebookText,
  RotateCcw,
  ShieldCheck,
  Sigma,
} from 'lucide-react'
import { LANDING_CONTENT, type PillarTab } from '../../data/landingContent'
import { EASE_OUT, Reveal } from './motion'

// Three tabs (Spend, Truth, Local). Each shows a live mockup on the left and
// three feature rows on the right. Tabs advance on their own while the section
// is on screen, and stop advancing once the reader picks one.

const ICONS: Record<PillarTab['rows'][number]['icon'], LucideIcon> = {
  gauge: Gauge,
  fingerprint: Fingerprint,
  ledger: NotebookText,
  interval: Sigma,
  agree: GitCompare,
  null: Activity,
  shield: ShieldCheck,
  eraser: Eraser,
  replay: RotateCcw,
}

const CYCLE_MS = 7000

const stagger = (reduce: boolean | null, gap = 0.12, delay = 0.25): Variants => ({
  hidden: {},
  show: { transition: { staggerChildren: reduce ? 0 : gap, delayChildren: reduce ? 0 : delay } },
})
const rise = (reduce: boolean | null): Variants => ({
  hidden: reduce ? { opacity: 1 } : { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0, transition: { duration: 0.45, ease: EASE_OUT } },
})

// ---------- mockups ----------

const SpendMock: React.FC = () => {
  const reduce = useReducedMotion()
  const ceilings = [
    { label: 'Total', cap: '$5.00', used: 0.18 },
    { label: 'Pilot', cap: '$1.00', used: 0.42 },
    { label: 'Per run', cap: '$1.00', used: 0.09 },
  ]
  const ledger = [
    { tx: 'tx-7c21', basis: 'ACTUAL', amt: '$0.0031' },
    { tx: 'tx-7c22', basis: 'ESTIMATED', amt: '$0.0024' },
    { tx: 'tx-7c23', basis: 'UNAVAILABLE', amt: '$0.0000' },
    { tx: 'tx-7c24', basis: 'UNRESOLVED', amt: '—', flag: true },
  ]
  return (
    <motion.div className="rp-pl-mock" initial="hidden" animate="show" variants={stagger(reduce, 0.1, 0.15)}>
      <motion.p className="rp-pl-mock-kicker" variants={rise(reduce)}>Budget</motion.p>
      <motion.p className="rp-pl-mock-title" variants={rise(reduce)}>Ceilings &amp; ledger</motion.p>
      <motion.div className="rp-pl-gauges" variants={rise(reduce)}>
        {ceilings.map((c, i) => (
          <div key={c.label} className="rp-pl-gauge">
            <span>{c.label}</span>
            <span className="rp-pl-track">
              <motion.i
                initial={{ scaleX: reduce ? c.used : 0 }}
                animate={{ scaleX: c.used }}
                transition={{ duration: reduce ? 0 : 1, delay: reduce ? 0 : 0.35 + i * 0.12, ease: EASE_OUT }}
              />
            </span>
            <span className="is-dim">{c.cap}</span>
          </div>
        ))}
      </motion.div>
      {ledger.map((r) => (
        <motion.div key={r.tx} className={`rp-pl-row${r.flag ? ' is-flag' : ''}`} variants={rise(reduce)}>
          <span className="rp-pl-mono">{r.tx}</span>
          <span className="rp-pl-tag">{r.basis}</span>
          <span className="rp-pl-mono rp-pl-right">{r.amt}</span>
        </motion.div>
      ))}
      <motion.p className="rp-pl-banner" variants={rise(reduce)}>
        Live runs blocked · reconcile tx-7c24
      </motion.p>
    </motion.div>
  )
}

const TruthMock: React.FC = () => {
  const reduce = useReducedMotion()
  const cases = [
    { id: 'case-014', acc: '1.00' },
    { id: 'case-015', acc: '0.62' },
    { id: 'case-016', acc: '—', note: 'unlabelled' },
    { id: 'case-017', acc: '0.88' },
  ]
  return (
    <motion.div className="rp-pl-mock" initial="hidden" animate="show" variants={stagger(reduce, 0.1, 0.15)}>
      <motion.p className="rp-pl-mock-kicker" variants={rise(reduce)}>Scorecard</motion.p>
      <motion.p className="rp-pl-mock-title" variants={rise(reduce)}>Accuracy</motion.p>
      <motion.div className="rp-pl-stat" variants={rise(reduce)}>
        <span className="rp-pl-big">0.84</span>
        <span className="rp-pl-ci">
          <span className="rp-pl-ci-bar">
            <motion.i
              initial={{ scaleX: reduce ? 1 : 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: reduce ? 0 : 0.9, delay: reduce ? 0 : 0.4, ease: EASE_OUT }}
            />
            <b />
          </span>
          <span className="is-dim">Wilson 95% · 0.71–0.92 · n = 50</span>
        </span>
      </motion.div>
      {cases.map((c) => (
        <motion.div key={c.id} className="rp-pl-row" variants={rise(reduce)}>
          <span className="rp-pl-mono">{c.id}</span>
          <span className="is-dim">{c.note ?? 'labelled'}</span>
          <span className="rp-pl-mono rp-pl-right">{c.acc}</span>
        </motion.div>
      ))}
      <motion.div className="rp-pl-row rp-pl-row-plain" variants={rise(reduce)}>
        <span>Agreement κ</span>
        <span className="is-dim">reported as agreement</span>
        <span className="rp-pl-mono rp-pl-right">0.61</span>
      </motion.div>
    </motion.div>
  )
}

const LocalMock: React.FC = () => {
  const reduce = useReducedMotion()
  const lines: { t: string; tone?: string }[] = [
    { t: '$ uv run runport validate-dataset', tone: 'cmd' },
    { t: '  eligible for external dispatch   6', tone: 'dim' },
    { t: '  blocked from outbound network    0', tone: 'dim' },
    { t: '✓ dataset validation passed', tone: 'ok' },
    { t: '$ uv run runport benchmark --live', tone: 'cmd' },
    { t: '✗ privacy gate rejected case c-17:', tone: 'bad' },
    { t: "  forbidden field 'email' · 0 requests sent", tone: 'dim' },
    { t: '  telemetry: none · data: ./data/runport.db', tone: 'dim' },
  ]
  return (
    <motion.div className="rp-pl-mock rp-pl-term" initial="hidden" animate="show" variants={stagger(reduce, 0.22, 0.2)}>
      {lines.map((l, i) => (
        <motion.p key={i} className={l.tone ? `is-${l.tone}` : undefined} variants={rise(reduce)}>
          {l.t}
        </motion.p>
      ))}
    </motion.div>
  )
}

const MOCKS: Record<PillarTab['key'], React.FC> = { spend: SpendMock, truth: TruthMock, local: LocalMock }

// ---------- section ----------

export const Pillars: React.FC = () => {
  const c = LANDING_CONTENT.pillars
  const reduce = useReducedMotion()
  const [active, setActive] = useState(0)
  const [auto, setAuto] = useState(!reduce)
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { margin: '-20% 0px -20% 0px' })

  useEffect(() => {
    if (!auto || !inView) return
    const t = window.setTimeout(() => setActive((i) => (i + 1) % c.tabs.length), CYCLE_MS)
    return () => window.clearTimeout(t)
  }, [active, auto, inView, c.tabs.length])

  const tab = c.tabs[active]
  const Mock = MOCKS[tab.key]
  const fade = reduce
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0.15 } }
    : {
        initial: { opacity: 0, y: 14, filter: 'blur(6px)' },
        animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
        exit: { opacity: 0, y: -10, filter: 'blur(6px)' },
        transition: { duration: 0.45, ease: EASE_OUT },
      }

  return (
    <section className="rp-section rp-pl" id="why" aria-labelledby="rp-pl-title">
      <div className="rp-pl-inner" ref={ref}>
        <Reveal className="rp-pl-head">
          <h2 id="rp-pl-title" className="rp-h2 rp-fade-heading">
            {c.titleA} {c.titleB}
          </h2>
          <p className="rp-body">{c.subheading}</p>
        </Reveal>

        <Reveal delay={0.08} className="rp-pl-tabs" role="tablist" aria-label="Why Runport">
          {c.tabs.map((t, i) => (
            <button
              key={t.key}
              type="button"
              role="tab"
              id={`rp-pl-tab-${t.key}`}
              aria-selected={i === active}
              aria-controls="rp-pl-panel"
              className={`rp-pl-tab${i === active ? ' is-active' : ''}`}
              onClick={() => {
                setActive(i)
                setAuto(false)
              }}
            >
              {i === active && <motion.span layoutId="rp-pl-pill" className="rp-pl-tab-bg" transition={{ duration: 0.4, ease: EASE_OUT }} />}
              <span className="rp-pl-tab-label">{t.label}</span>
              {i === active && auto && inView && (
                <motion.span
                  key={`p-${active}`}
                  className="rp-pl-tab-progress"
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ duration: CYCLE_MS / 1000, ease: 'linear' }}
                />
              )}
            </button>
          ))}
        </Reveal>

        <Reveal delay={0.12}>
          <div className="rp-pl-body" id="rp-pl-panel" role="tabpanel" aria-labelledby={`rp-pl-tab-${tab.key}`}>
            <div className="rp-pl-media">
              <img className="rp-pl-art" src="/assets/landing/testimonial-bg.jpg" alt="" loading="lazy" />
              <AnimatePresence mode="wait">
                <motion.div key={tab.key} className="rp-pl-window" {...fade}>
                  <Mock />
                </motion.div>
              </AnimatePresence>
              <span className="rp-pl-sample">Sample</span>
            </div>
            <AnimatePresence mode="wait">
              <motion.div key={tab.key} className="rp-pl-copy" {...fade}>
                <p className="rp-pl-eyebrow">{tab.eyebrow}</p>
                <h3 className="rp-pl-title">{tab.title}</h3>
                <p className="rp-pl-text">{tab.body}</p>
                <motion.ul className="rp-pl-rows" initial="hidden" animate="show" variants={stagger(reduce, 0.1, 0.2)}>
                  {tab.rows.map((r) => {
                    const Icon = ICONS[r.icon]
                    return (
                      <motion.li key={r.title} className="rp-pl-feature" variants={rise(reduce)}>
                        <span className="rp-pl-icon" aria-hidden="true">
                          <Icon size={15} strokeWidth={1.7} />
                        </span>
                        <span>
                          <strong>{r.title}</strong>
                          <span>{r.body}</span>
                        </span>
                      </motion.li>
                    )
                  })}
                </motion.ul>
              </motion.div>
            </AnimatePresence>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
