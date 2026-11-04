import React, { useEffect, useRef, useState } from 'react'
import { animate, motion, useInView, useReducedMotion } from 'framer-motion'
import { Activity, Cpu, Database, GitCompare, Wallet, Workflow, type LucideIcon } from 'lucide-react'
import { LANDING_CONTENT, type CarouselCard } from '../../data/landingContent'
import { EASE_OUT, Reveal } from './motion'

// "Everything a benchmark needs": a bento grid. Each tile carries a small live
// visual of what the feature does (a leaderboard, a spend ring, a secret being
// redacted, a hash re-checking itself, requests flowing into one result shape,
// and diverging deltas between two runs). A soft spotlight follows the cursor.
// Values are illustrative ("Sample") and mirror shipped behaviour.

const ICONS: Record<CarouselCard['icon'], LucideIcon> = {
  cpu: Cpu,
  workflow: Workflow,
  database: Database,
  wallet: Wallet,
  activity: Activity,
  'git-compare': GitCompare,
}
const LOGOS = '/assets/landing/logos'
const VIEW = { once: true, margin: '0px 0px -12% 0px' } as const

/** Runs `fn` every `ms` while the element is on screen (skipped for reduced motion). */
function useLoop(ref: React.RefObject<Element>, ms: number, fn: () => void, enabled = true) {
  const inView = useInView(ref, { margin: '-10% 0px -10% 0px' })
  const reduce = useReducedMotion()
  useEffect(() => {
    if (!inView || reduce || !enabled) return
    const t = window.setInterval(fn, ms)
    return () => window.clearInterval(t)
  }, [inView, reduce, ms, enabled]) // eslint-disable-line react-hooks/exhaustive-deps
}

// ---------- visuals ----------

const Leaderboard: React.FC = () => {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, VIEW)
  const rows = [
    { name: 'gpt-4o-mini', acc: 0.913, cost: '$0.13', basis: 'ESTIMATED' },
    { name: 'claude-3-5-haiku', acc: 0.886, cost: '$0.49', basis: 'ACTUAL' },
    { name: 'llama3.1 · ollama', acc: 0.742, cost: '$0.00', basis: 'UNAVAILABLE' },
  ]
  return (
    <div className="rp-bx-board" ref={ref}>
      <div className="rp-bx-board-head">
        <span>#</span>
        <span>Model</span>
        <span className="rp-bx-hide-sm" />
        <span className="rp-bx-right">Accuracy</span>
        <span className="rp-bx-right">Cost / 1k</span>
        <span className="rp-bx-right rp-bx-hide-sm">Basis</span>
      </div>
      {rows.map((r, i) => (
        <motion.div
          key={r.name}
          className="rp-bx-board-row"
          initial={reduce ? false : { opacity: 0, x: -10 }}
          animate={inView || reduce ? { opacity: 1, x: 0 } : undefined}
          transition={{ duration: 0.5, delay: 0.15 + i * 0.12, ease: EASE_OUT }}
        >
          <span className="rp-bx-rank">{i + 1}</span>
          <span className="rp-bx-name">{r.name}</span>
          <span className="rp-bx-bar">
            <motion.i
              initial={{ scaleX: reduce ? r.acc : 0 }}
              animate={inView || reduce ? { scaleX: r.acc } : undefined}
              transition={{ duration: reduce ? 0 : 1.2, delay: reduce ? 0 : 0.35 + i * 0.12, ease: EASE_OUT }}
            />
          </span>
          <span className="rp-bx-num">{(r.acc * 100).toFixed(1)}%</span>
          <span className="rp-bx-num">{r.cost}</span>
          <span className="rp-bx-tag">{r.basis}</span>
        </motion.div>
      ))}
    </div>
  )
}

const SpendRing: React.FC = () => {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, VIEW)
  const used = 0.182
  const [shown, setShown] = useState(reduce ? used * 5 : 0)
  useEffect(() => {
    if (!inView || reduce) return
    const c = animate(0, used * 5, { duration: 1.6, ease: EASE_OUT, onUpdate: setShown })
    return () => c.stop()
  }, [inView, reduce])
  const R = 52
  const C = 2 * Math.PI * R
  return (
    <div className="rp-bx-ring" ref={ref}>
      <svg viewBox="0 0 140 140" aria-hidden="true">
        <circle cx="70" cy="70" r={R} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="8" />
        <circle cx="70" cy="70" r={R} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="8" strokeDasharray={`2 ${C / 40 - 2}`} />
        <motion.circle
          cx="70"
          cy="70"
          r={R}
          fill="none"
          stroke="#ffffff"
          strokeWidth="8"
          strokeLinecap="round"
          transform="rotate(-90 70 70)"
          strokeDasharray={C}
          initial={{ strokeDashoffset: reduce ? C * (1 - used) : C }}
          animate={inView ? { strokeDashoffset: C * (1 - used) } : undefined}
          transition={{ duration: reduce ? 0 : 1.6, ease: EASE_OUT }}
        />
      </svg>
      <div className="rp-bx-ring-label">
        <strong>${shown.toFixed(2)}</strong>
        <span>of $5.00 total</span>
      </div>
      <ul className="rp-bx-caps">
        <li>
          <span>Pilot</span>
          <span>$1.00</span>
        </li>
        <li>
          <span>Per run</span>
          <span>$1.00</span>
        </li>
        <li>
          <span>Per case</span>
          <span>$0.05</span>
        </li>
        <li className="is-ok">
          <span>Unresolved</span>
          <span>0</span>
        </li>
      </ul>
    </div>
  )
}

const SECRET = 'sk-or-v1-8f3a2c91d7'
const Redaction: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const reduce = useReducedMotion()
  const [redacted, setRedacted] = useState(!!reduce)
  useEffect(() => {
    if (reduce) return
    setRedacted(false)
    const t = window.setTimeout(() => setRedacted(true), 1400)
    return () => window.clearTimeout(t)
  }, [reduce])
  useLoop(ref, 4200, () => {
    setRedacted(false)
    window.setTimeout(() => setRedacted(true), 1400)
  })
  return (
    <div className="rp-bx-code" ref={ref}>
      <p>
        <span className="k">POST</span> /api/v1/chat/completions
      </p>
      <p>
        authorization: Bearer{' '}
        <span className={`rp-bx-secret${redacted ? ' is-red' : ''}`}>
          <motion.span
            key={redacted ? 'r' : 's'}
            initial={reduce ? false : { opacity: 0, filter: 'blur(4px)' }}
            animate={{ opacity: 1, filter: 'blur(0px)' }}
            transition={{ duration: 0.35 }}
          >
            {redacted ? '[REDACTED]' : SECRET}
          </motion.span>
        </span>
      </p>
      <p>
        model: <span className="s">"claude-3-5-haiku"</span>
      </p>
      <p>
        usage: {'{'} prompt: 214, completion: 87 {'}'}
      </p>
      <p className="c">cost_usd: 0.0004 · ACTUAL</p>
    </div>
  )
}

const HEX = '0123456789abcdef'
const HASH = 'c07a5e19b2d4f0a83e61'
const HashCheck: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const reduce = useReducedMotion()
  const [text, setText] = useState(HASH)
  const [settled, setSettled] = useState(true)
  const run = () => {
    setSettled(false)
    let frame = 0
    const t = window.setInterval(() => {
      frame += 1
      const fixed = Math.floor((frame / 18) * HASH.length)
      setText(HASH.split('').map((ch, i) => (i < fixed ? ch : HEX[Math.floor(Math.random() * 16)])).join(''))
      if (fixed >= HASH.length) {
        window.clearInterval(t)
        setText(HASH)
        setSettled(true)
      }
    }, 45)
  }
  useLoop(ref, 4600, run)
  return (
    <div className="rp-bx-hash" ref={ref}>
      <div className="rp-bx-hash-row">
        <span>before run</span>
        <code>sha256:{HASH}</code>
      </div>
      <div className="rp-bx-hash-row">
        <span>after run</span>
        <code className={settled ? 'is-ok' : undefined}>sha256:{reduce ? HASH : text}</code>
      </div>
      <p className={`rp-bx-verdict${settled ? ' is-ok' : ''}`}>{settled ? '✓ source unchanged' : 'verifying…'}</p>
    </div>
  )
}

const Flow: React.FC = () => {
  const reduce = useReducedMotion()
  const sources = [
    { logo: 'dify.svg', y: 18 },
    { logo: 'n8n.svg', y: 50 },
    { logo: 'langgraph.svg', y: 82 },
    { logo: 'flowise.png', y: 114 },
  ]
  return (
    <div className="rp-bx-flow">
      <svg viewBox="0 0 300 132" aria-hidden="true">
        {sources.map((s, i) => {
          const d = `M44 ${s.y} C 130 ${s.y}, 150 66, 214 66`
          return (
            <g key={s.logo}>
              <path d={d} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="1.2" />
              {!reduce && (
                <circle r="2.6" fill="#fff" opacity="0">
                  <animateMotion dur="1.8s" repeatCount="indefinite" begin={`${i * 0.45}s`} path={d} keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.4 0 0.2 1" />
                  <animate attributeName="opacity" dur="1.8s" repeatCount="indefinite" begin={`${i * 0.45}s`} values="0;1;1;0" keyTimes="0;0.15;0.85;1" />
                </circle>
              )}
              <rect x="10" y={s.y - 14} width="28" height="28" rx="7" fill="#131315" stroke="rgba(255,255,255,0.12)" />
              <image href={`${LOGOS}/${s.logo}`} x="17" y={s.y - 7} width="14" height="14" />
            </g>
          )
        })}
        <rect x="214" y="48" width="78" height="36" rx="8" fill="#151517" stroke="rgba(255,255,255,0.2)" />
        <text x="253" y="70" textAnchor="middle" fontFamily="'Intel One Mono', ui-monospace, monospace" fontSize="9.5" fill="rgba(255,255,255,0.85)">
          TargetResult
        </text>
      </svg>
    </div>
  )
}

const Deltas: React.FC = () => {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, VIEW)
  const rows = [
    { label: 'Accuracy', a: '91.3%', b: '88.6%', d: -2.7, unit: '%' },
    { label: 'p50 latency', a: '402 ms', b: '348 ms', d: -54, unit: ' ms', better: true },
    { label: 'Tokens / case', a: '301', b: '274', d: -27, unit: '' },
    { label: 'Cost / 1k', a: '$0.13', b: '$0.49', d: 0.36, unit: '', money: true },
  ]
  const max = { Accuracy: 5, 'p50 latency': 100, 'Tokens / case': 50, 'Cost / 1k': 0.5 } as Record<string, number>
  return (
    <div className="rp-bx-deltas" ref={ref}>
      <div className="rp-bx-deltas-head">
        <span />
        <span>Run A</span>
        <span>Run B</span>
        <span className="rp-bx-axis-label">B − A</span>
      </div>
      {rows.map((r, i) => {
        const w = Math.min(1, Math.abs(r.d) / max[r.label]) * 50
        const right = r.d > 0
        return (
          <div key={r.label} className="rp-bx-delta-row">
            <span className="rp-bx-name">{r.label}</span>
            <span className="rp-bx-num">{r.a}</span>
            <span className="rp-bx-num">{r.b}</span>
            <span className="rp-bx-axis">
              <motion.i
                className={right ? 'is-right' : 'is-left'}
                style={{ width: `${w}%`, [right ? 'left' : 'right']: '50%' } as React.CSSProperties}
                initial={{ scaleX: reduce ? 1 : 0 }}
                animate={inView || reduce ? { scaleX: 1 } : undefined}
                transition={{ duration: reduce ? 0 : 0.9, delay: reduce ? 0 : 0.25 + i * 0.1, ease: EASE_OUT }}
              />
              <em style={{ [right ? 'left' : 'right']: `calc(50% + ${w}% + 6px)` } as React.CSSProperties}>
                {r.money ? `+$${r.d.toFixed(2)}` : `${r.d > 0 ? '+' : ''}${r.d}${r.unit}`}
              </em>
            </span>
          </div>
        )
      })}
    </div>
  )
}

const VISUALS: Record<CarouselCard['icon'], React.FC> = {
  cpu: Leaderboard,
  wallet: SpendRing,
  activity: Redaction,
  database: HashCheck,
  workflow: Flow,
  'git-compare': Deltas,
}

// Grid placement (desktop): models wide, budgets tall, compare wide.
const AREA: Record<CarouselCard['icon'], string> = {
  cpu: 'models',
  wallet: 'budgets',
  activity: 'traces',
  database: 'datasets',
  workflow: 'workflows',
  'git-compare': 'compare',
}

const Tile: React.FC<{ card: CarouselCard; index: number }> = ({ card, index }) => {
  const Icon = ICONS[card.icon]
  const Visual = VISUALS[card.icon]
  const onMove = (e: React.MouseEvent<HTMLElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    e.currentTarget.style.setProperty('--mx', `${e.clientX - r.left}px`)
    e.currentTarget.style.setProperty('--my', `${e.clientY - r.top}px`)
  }
  return (
    <Reveal delay={0.05 * index} className={`rp-bx-tile rp-bx-${AREA[card.icon]}`} onMouseMove={onMove}>
      <div className="rp-bx-visual">
        <Visual />
      </div>
      <div className="rp-bx-copy">
        <h3>
          <Icon size={16} strokeWidth={1.7} aria-hidden="true" />
          {card.title}
        </h3>
        <p>{card.body}</p>
      </div>
    </Reveal>
  )
}

export const FeatureBento: React.FC = () => {
  const c = LANDING_CONTENT.carousel
  return (
    <section id="features" className="rp-section rp-bx">
      <div className="rp-bx-inner">
        <Reveal className="rp-bx-head">
          <h2 className="rp-h2 rp-fade-heading">
            {c.titleA}
            <br />
            {c.titleB}
          </h2>
        </Reveal>
        <div className="rp-bx-grid">
          {c.cards.map((card, i) => (
            <Tile key={card.icon} card={card} index={i} />
          ))}
        </div>
        <p className="rp-bx-note">Sample values. Every tile mirrors a shipped feature.</p>
      </div>
    </section>
  )
}
