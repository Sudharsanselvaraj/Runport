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

// ---------- visuals (minimal: one idea per tile, no nested boxes) ----------

const Leaderboard: React.FC = () => {
  const reduce = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, VIEW)
  const rows = [
    { name: 'gpt-4o-mini', acc: 0.913, cost: '$0.13' },
    { name: 'claude-3-5-haiku', acc: 0.886, cost: '$0.49' },
    { name: 'llama3.1 · local', acc: 0.742, cost: '$0.00' },
  ]
  return (
    <div className="rp-bx-board" ref={ref}>
      {rows.map((r, i) => (
        <div key={r.name} className="rp-bx-board-row">
          <span className="rp-bx-name">{r.name}</span>
          <span className="rp-bx-bar">
            <motion.i
              initial={{ scaleX: reduce ? r.acc : 0 }}
              animate={inView || reduce ? { scaleX: r.acc } : undefined}
              transition={{ duration: reduce ? 0 : 1.2, delay: reduce ? 0 : 0.2 + i * 0.12, ease: EASE_OUT }}
            />
          </span>
          <span className="rp-bx-num">{(r.acc * 100).toFixed(1)}%</span>
          <span className="rp-bx-num rp-bx-dim">{r.cost}</span>
        </div>
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
  const R = 54
  const C = 2 * Math.PI * R
  return (
    <div className="rp-bx-ring" ref={ref}>
      <div className="rp-bx-ring-gauge">
        <svg viewBox="0 0 140 140" aria-hidden="true">
          <circle cx="70" cy="70" r={R} fill="none" stroke="rgba(255,255,255,0.07)" strokeWidth="3" />
          <motion.circle
            cx="70"
            cy="70"
            r={R}
            fill="none"
            stroke="#ffffff"
            strokeWidth="3"
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
          <span>of $5.00</span>
        </div>
      </div>
      <ul className="rp-bx-caps">
        <li>
          <span>Per run</span>
          <span>$1.00</span>
        </li>
        <li>
          <span>Per case</span>
          <span>$0.05</span>
        </li>
        <li>
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
    const t = window.setTimeout(() => setRedacted(true), 1400)
    return () => window.clearTimeout(t)
  }, [reduce])
  useLoop(ref, 4200, () => {
    setRedacted(false)
    window.setTimeout(() => setRedacted(true), 1400)
  })
  return (
    <div className="rp-bx-code" ref={ref}>
      <p className="rp-bx-dim">POST /v1/chat/completions</p>
      <p>
        <span className="rp-bx-dim">authorization </span>
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
      <p className="rp-bx-dim">cost_usd 0.0004 · ACTUAL</p>
    </div>
  )
}

const HEX = '0123456789abcdef'
const HASH = 'c07a5e19b2d4f0a8'
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
      <p>
        <span className="rp-bx-dim">before</span>
        <code>{HASH}</code>
      </p>
      <p>
        <span className="rp-bx-dim">after</span>
        <code>{reduce ? HASH : text}</code>
      </p>
      <p className={`rp-bx-verdict${settled ? ' is-ok' : ''}`}>{settled ? 'unchanged' : 'verifying'}</p>
    </div>
  )
}

const Flow: React.FC = () => {
  const reduce = useReducedMotion()
  const sources = [
    { logo: 'dify.svg', y: 20 },
    { logo: 'n8n.svg', y: 52 },
    { logo: 'langgraph.svg', y: 84 },
    { logo: 'flowise.png', y: 116 },
  ]
  return (
    <div className="rp-bx-flow">
      <svg viewBox="0 0 300 136" aria-hidden="true">
        {sources.map((s, i) => {
          const d = `M40 ${s.y} C 120 ${s.y}, 150 68, 218 68`
          return (
            <g key={s.logo}>
              <path d={d} fill="none" stroke="rgba(255,255,255,0.09)" strokeWidth="1" />
              {!reduce && (
                <circle r="2" fill="#fff" opacity="0">
                  <animateMotion dur="2.2s" repeatCount="indefinite" begin={`${i * 0.55}s`} path={d} keyPoints="0;1" keyTimes="0;1" calcMode="spline" keySplines="0.4 0 0.2 1" />
                  <animate attributeName="opacity" dur="2.2s" repeatCount="indefinite" begin={`${i * 0.55}s`} values="0;0.9;0.9;0" keyTimes="0;0.15;0.85;1" />
                </circle>
              )}
              <image href={`${LOGOS}/${s.logo}`} x="18" y={s.y - 8} width="16" height="16" opacity="0.85" />
            </g>
          )
        })}
        <text x="226" y="72" fontFamily="'Intel One Mono', ui-monospace, monospace" fontSize="10" fill="rgba(255,255,255,0.75)">
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
    { label: 'Accuracy', d: -2.7, max: 5, text: '−2.7%' },
    { label: 'p50 latency', d: -54, max: 100, text: '−54 ms' },
    { label: 'Cost / 1k', d: 0.36, max: 0.5, text: '+$0.36' },
  ]
  return (
    <div className="rp-bx-deltas" ref={ref}>
      <div className="rp-bx-deltas-legend">
        <span>Run A</span>
        <span className="rp-bx-dim">vs</span>
        <span>Run B</span>
      </div>
      {rows.map((r, i) => {
        const w = Math.min(1, Math.abs(r.d) / r.max) * 50
        const right = r.d > 0
        return (
          <div key={r.label} className="rp-bx-delta-row">
            <span className="rp-bx-name">{r.label}</span>
            <span className="rp-bx-axis">
              <motion.i
                className={right ? 'is-right' : 'is-left'}
                style={{ width: `${w}%`, [right ? 'left' : 'right']: '50%' } as React.CSSProperties}
                initial={{ scaleX: reduce ? 1 : 0 }}
                animate={inView || reduce ? { scaleX: 1 } : undefined}
                transition={{ duration: reduce ? 0 : 0.9, delay: reduce ? 0 : 0.2 + i * 0.1, ease: EASE_OUT }}
              />
            </span>
            <span className="rp-bx-num">{r.text}</span>
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
          <Icon size={15} strokeWidth={1.6} aria-hidden="true" />
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
          <p className="rp-eyebrow">Features</p>
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
        <p className="rp-bx-note">Sample values</p>
      </div>
    </section>
  )
}
