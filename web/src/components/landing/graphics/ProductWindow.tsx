import React, { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Check, Circle, Lock, Pause, Play } from 'lucide-react'
import {
  AGREEMENT,
  BUDGET_DEFAULTS,
  CANDIDATES,
  CLASSES,
  LIVE_RUN,
  PLAN,
  RESULTS,
  SCORE_EXTRAS,
  eventCell,
  formatAmount,
  formatUsd,
  pct,
  perClassRecall,
  wilson,
  type Provenance,
} from '../../../data/sampleRun'
import { SampleChip } from '../SampleChip'
import { useLoopWhenVisible } from '../motionKit'

// A premium macOS-style product window that showcases Runport's real dashboard.
// Automatically transitions through Plan -> Live Run -> Results every 4.5 seconds
// with smooth crossfading and subtle horizontal drift.
//
// Pauses on hover, focus, or manual interaction.
// Respects prefers-reduced-motion (stops auto-advance, zero horizontal movement).
// Features a smooth bottom gradient fade that dissolves seamlessly into the website background.

const TABS = ['Plan', 'Live Run', 'Results'] as const
type Tab = (typeof TABS)[number]
const CYCLE_MS = 4500

// The seven runner safeguards, in the order the runner enforces them.
const GUARDS = [
  'Authorization',
  'Privacy gate',
  'Preflight budget',
  'Transport',
  'Validation',
  'Persistence',
  'Spend booking',
]

const Prov: React.FC<{ p: Provenance }> = ({ p }) => (
  <span className={`rp-pw-prov is-${p.toLowerCase()}`}>{p}</span>
)

const money = (v: number | null) => (v === null ? '—' : formatUsd(v, 2))

// --- SCREEN A: PLAN ---
const PlanTab: React.FC = () => (
  <div className="rp-pw-grid">
    <section className="rp-pw-block rp-pw-span2">
      <h3>Candidates</h3>
      <div className="rp-pw-table-wrap">
        <table className="rp-pw-table">
          <thead>
            <tr>
              <th>Target</th>
              <th>Route</th>
              <th className="r">In / 1M</th>
              <th className="r">Out / 1M</th>
            </tr>
          </thead>
          <tbody>
            {CANDIDATES.map((c) => (
              <tr key={c.id}>
                <td>{c.id}</td>
                <td className="mono">{c.route}</td>
                <td className={`r${c.inPer1M === null ? ' is-null' : ''}`}>{money(c.inPer1M)}</td>
                <td className={`r${c.outPer1M === null ? ' is-null' : ''}`}>{money(c.outPer1M)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
    <section className="rp-pw-block">
      <h3>Ceilings</h3>
      <dl className="rp-pw-dl">
        <div>
          <dt>Total</dt>
          <dd>{formatUsd(BUDGET_DEFAULTS.totalUsd, 2)}</dd>
        </div>
        <div>
          <dt>Per run</dt>
          <dd>{formatUsd(BUDGET_DEFAULTS.perRunUsd, 2)}</dd>
        </div>
        <div>
          <dt>Per case</dt>
          <dd>{formatUsd(BUDGET_DEFAULTS.perCaseUsd, 2)}</dd>
        </div>
      </dl>
      <h3 className="rp-pw-gap">Fingerprint</h3>
      <code className="rp-pw-code">{PLAN.fingerprint}</code>
      <p className="rp-pw-note">
        {PLAN.split} split · {PLAN.cases} cases · {PLAN.template}
      </p>
    </section>
  </div>
)

// --- SCREEN B: LIVE RUN ---
const RunTab: React.FC = () => {
  const done = Math.round((LIVE_RUN.done / LIVE_RUN.total) * 100)
  return (
    <div className="rp-pw-grid">
      <section className="rp-pw-block rp-pw-span3">
        <div className="rp-pw-row">
          <h3>
            {LIVE_RUN.id} · {LIVE_RUN.done} / {LIVE_RUN.total}
          </h3>
          <span className="rp-pw-num">{done}%</span>
        </div>
        <div className="rp-pw-bar">
          <i style={{ width: `${done}%` }} />
        </div>
        <ol className="rp-pw-guards" aria-label="Runner guard order">
          {GUARDS.map((g, i) => (
            <li key={g} className={i < 6 ? 'is-done' : 'is-now'}>
              {i < 6 ? <Check size={11} aria-hidden="true" /> : <Circle size={9} aria-hidden="true" />}
              {g}
            </li>
          ))}
        </ol>
      </section>
      <section className="rp-pw-block rp-pw-span3">
        <div className="rp-pw-table-wrap">
          <table className="rp-pw-table">
            <thead>
              <tr>
                <th>Case</th>
                <th>Target</th>
                <th className="r">Latency</th>
                <th className="r">Tokens</th>
                <th className="r">Cost</th>
                <th>Provenance</th>
              </tr>
            </thead>
            <tbody>
              {LIVE_RUN.events.map(([id, target, ms, tin, tout], i) => {
                const cell = eventCell(target, tin, tout)
                const amount = formatAmount(cell)
                const tokens = tin === null || tout === null ? '—' : String(tin + tout)
                return (
                  <tr key={i}>
                    <td className="mono">{id}</td>
                    <td>{target}</td>
                    <td className="r">{ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms} ms`}</td>
                    <td className={`r${tokens === '—' ? ' is-null' : ''}`}>{tokens}</td>
                    <td className={`r${amount.startsWith('$') ? '' : ' is-null'}`}>{amount}</td>
                    <td>
                      <Prov p={cell.provenance} />
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  )
}

// --- SCREEN C: RESULTS ---
const ResultsTab: React.FC = () => {
  const r = RESULTS[AGREEMENT.a]
  const [lo, hi] = wilson(r.correct, PLAN.cases)
  const recall = perClassRecall()
  return (
    <div className="rp-pw-grid">
      <section className="rp-pw-block">
        <h3>Accuracy · {AGREEMENT.a}</h3>
        <p className="rp-pw-big">{pct(r.correct, PLAN.cases)}</p>
        <p className="rp-pw-note">
          Wilson 95% {(lo * 100).toFixed(1)}–{(hi * 100).toFixed(1)}% · human-approved labels
        </p>
      </section>
      <section className="rp-pw-block">
        <h3>Macro F1 · Brier</h3>
        <p className="rp-pw-big">{SCORE_EXTRAS.macroF1.toFixed(3)}</p>
        <p className="rp-pw-note">Brier {SCORE_EXTRAS.brier.toFixed(3)} · thresholds frozen on DEV</p>
      </section>
      <section className="rp-pw-block">
        <h3>Agreement κ</h3>
        <p className="rp-pw-big">{AGREEMENT.kappa.toFixed(2)}</p>
        <p className="rp-pw-note">vs {AGREEMENT.b} · not accuracy</p>
      </section>
      <section className="rp-pw-block rp-pw-span3">
        <h3>Per-class recall</h3>
        <div className="rp-pw-cls-list">
          {CLASSES.map((c, i) => (
            <div key={c} className="rp-pw-cls">
              <span>{c}</span>
              <span className="rp-pw-bar">
                <i style={{ width: `${recall[i]}%` }} />
              </span>
              <b>{recall[i].toFixed(1)}%</b>
            </div>
          ))}
        </div>
      </section>
    </div>
  )
}

const PANELS: Record<Tab, React.FC> = { Plan: PlanTab, 'Live Run': RunTab, Results: ResultsTab }

export const ProductWindow: React.FC = () => {
  const frameRef = useRef<HTMLDivElement>(null)
  const reduced = useReducedMotion()
  const { active } = useLoopWhenVisible(frameRef)
  const [tab, setTab] = useState<Tab>('Plan')
  const [direction, setDirection] = useState(1)
  const [hold, setHold] = useState(false)
  const [paused, setPaused] = useState(false)

  const cycling = active && !hold && !paused && !reduced

  useEffect(() => {
    if (!cycling) return
    const t = window.setTimeout(() => {
      setDirection(1)
      setTab((curr) => {
        const nextIdx = (TABS.indexOf(curr) + 1) % TABS.length
        return TABS[nextIdx]
      })
    }, CYCLE_MS)
    return () => window.clearTimeout(t)
  }, [cycling, tab])

  const selectTab = (nextTab: Tab) => {
    const curIdx = TABS.indexOf(tab)
    const nextIdx = TABS.indexOf(nextTab)
    if (curIdx === nextIdx) return
    setDirection(nextIdx > curIdx ? 1 : -1)
    setTab(nextTab)
    setPaused(true)
  }

  const onTabKey = (e: React.KeyboardEvent) => {
    const i = TABS.indexOf(tab)
    const next = {
      ArrowRight: (i + 1) % TABS.length,
      ArrowLeft: (i - 1 + TABS.length) % TABS.length,
      Home: 0,
      End: TABS.length - 1,
    }[e.key]
    if (next === undefined) return
    e.preventDefault()
    setDirection(next > i ? 1 : -1)
    setTab(TABS[next])
    document.getElementById(`rp-pw-tab-${next}`)?.focus()
  }

  const Panel = PANELS[tab]

  return (
    <div className="rp-pw-stage">
      <div
        ref={frameRef}
        className="rp-pw"
        onPointerEnter={() => setHold(true)}
        onPointerLeave={() => setHold(false)}
        onFocusCapture={() => setHold(true)}
        onBlurCapture={() => setHold(false)}
      >
        {/* macOS Chrome Header */}
        <div className="rp-pw-chrome">
          <div className="rp-pw-dots" aria-hidden="true">
            <span className="rp-pw-dot-red" />
            <span className="rp-pw-dot-yellow" />
            <span className="rp-pw-dot-green" />
          </div>
          <div className="rp-pw-url" title="Local Runport Web service">
            <Lock size={10} className="rp-pw-lock" aria-hidden="true" />
            <span>127.0.0.1:8000</span>
          </div>
          <div className="rp-pw-chip-wrap">
            <SampleChip />
          </div>
        </div>

        {/* Application Navigation Bar */}
        <div className="rp-pw-top">
          <div className="rp-pw-brand">
            <img src="/assets/landing/runport-emblem.png" alt="" width={18} height={18} />
            <span>Runport</span>
            <span className="rp-pw-crumb">
              {PLAN.name} {PLAN.version}
            </span>
          </div>
          <div className="rp-pw-tabs" role="tablist" aria-label="Workbench views" onKeyDown={onTabKey}>
            {TABS.map((t, i) => (
              <button
                key={t}
                id={`rp-pw-tab-${i}`}
                type="button"
                role="tab"
                aria-selected={tab === t}
                aria-controls="rp-pw-panel"
                tabIndex={tab === t ? 0 : -1}
                className={tab === t ? 'is-active' : undefined}
                onClick={() => selectTab(t)}
              >
                {t}
                {tab === t && cycling && <span key={tab} className="rp-pw-tab-timer" aria-hidden="true" />}
              </button>
            ))}
          </div>
          {!reduced && (
            <button
              type="button"
              className="rp-pw-pause"
              onClick={() => setPaused((p) => !p)}
              aria-label={paused ? 'Resume cycling the views' : 'Pause cycling the views'}
              title={paused ? 'Resume automatic transitions' : 'Pause automatic transitions'}
            >
              {paused ? <Play size={13} aria-hidden="true" /> : <Pause size={13} aria-hidden="true" />}
            </button>
          )}
        </div>

        {/* Animated Content Panel with smooth crossfade and subtle horizontal drift */}
        <div
          id="rp-pw-panel"
          role="tabpanel"
          aria-labelledby={`rp-pw-tab-${TABS.indexOf(tab)}`}
          className="rp-pw-panel"
        >
          <AnimatePresence mode="wait" initial={false}>
            <motion.div
              key={tab}
              initial={reduced ? { opacity: 0 } : { opacity: 0, x: direction * 12 }}
              animate={{ opacity: 1, x: 0 }}
              exit={reduced ? { opacity: 0 } : { opacity: 0, x: -direction * 12 }}
              transition={{
                duration: reduced ? 0 : 0.36,
                ease: [0.22, 1, 0.36, 1],
              }}
              className="rp-pw-slide"
            >
              <Panel />
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* Layered Bottom Fade Overlay for seamless dissolution into the website background */}
      <div className="rp-pw-fade-overlay" aria-hidden="true" />

      {/* Manual Pagination Indicators for Accessibility & Quick Navigation */}
      <div className="rp-pw-indicators" role="tablist" aria-label="Showcase screen indicators">
        {TABS.map((t, i) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={tab === t}
            className={`rp-pw-ind-pill${tab === t ? ' is-active' : ''}`}
            onClick={() => selectTab(t)}
            aria-label={`Switch to ${t} screen`}
          >
            <span className="rp-pw-ind-num">0{i + 1}</span>
            <span className="rp-pw-ind-name">{t}</span>
          </button>
        ))}
      </div>
    </div>
  )
}
