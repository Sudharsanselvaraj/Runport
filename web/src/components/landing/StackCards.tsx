import React, { useEffect, useRef, useState } from 'react'
import { motion, useInView, useReducedMotion } from 'framer-motion'
import { Check, Fingerprint, Lock, Table2, Terminal, X } from 'lucide-react'
import { LANDING_CONTENT, type StackCard } from '../../data/landingContent'
import { EASE_OUT, Reveal } from './motion'

// Four illustrated cards. Each illustration has a one-shot entrance (".is-in")
// and loops that only run while the card is on screen (".is-live"); the CSS
// pauses every loop otherwise and drops them under reduced motion.

const L = '/assets/landing/logos/'
const EMBLEM = '/assets/landing/runport-emblem.png'

function useStage<T extends Element>() {
  const ref = useRef<T>(null)
  const seen = useInView(ref, { once: true, margin: '0px 0px -15% 0px' })
  const live = useInView(ref, { margin: '-5% 0px -5% 0px' })
  const cls = `${seen ? ' is-in' : ''}${live ? ' is-live' : ''}`
  return { ref, seen, live, cls }
}

// ---------- 1. connects to the whole stack: orbit of real logos ----------
const W = 600
const H = 330
const CX = 300
const CY = 300
const RINGS = [84, 144, 204, 264]
const ORBIT: { ring: number; nodes: { logo: string; name: string; a: number }[] }[] = [
  { ring: 1, nodes: [{ logo: 'openai.svg', name: 'OpenAI', a: 132 }, { logo: 'ollama.svg', name: 'Ollama', a: 48 }] },
  {
    ring: 2,
    nodes: [
      { logo: 'anthropic.svg', name: 'Anthropic via OpenRouter', a: 156 },
      { logo: 'dify.svg', name: 'Dify', a: 92 },
      { logo: 'vllm.svg', name: 'vLLM', a: 26 },
    ],
  },
  {
    ring: 3,
    nodes: [
      { logo: 'gemini.svg', name: 'Gemini via OpenRouter', a: 164 },
      { logo: 'langgraph.svg', name: 'LangGraph', a: 121 },
      { logo: 'n8n.svg', name: 'n8n', a: 62 },
      { logo: 'langfuse.svg', name: 'Langfuse', a: 17 },
    ],
  },
]
const arc = (r: number) => `M ${CX - r} ${CY} A ${r} ${r} 0 0 1 ${CX + r} ${CY}`
const pos = (r: number, a: number) => {
  const t = (a * Math.PI) / 180
  return { left: `${((CX + r * Math.cos(t)) / W) * 100}%`, top: `${((CY - r * Math.sin(t)) / H) * 100}%` }
}

const OrbitArt: React.FC = () => {
  const s = useStage<HTMLDivElement>()
  return (
    <div ref={s.ref} className={`rp-sc-orbit${s.cls}`}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMax meet" aria-hidden="true">
        <defs>
          <linearGradient id="rp-sc-trail" x1="0" x2="1">
            <stop offset="0" stopColor="rgba(175,225,255,0)" />
            <stop offset="1" stopColor="rgba(175,225,255,0.9)" />
          </linearGradient>
        </defs>
        {RINGS.map((r, i) => (
          <g key={r} style={{ '--i': i } as React.CSSProperties}>
            <path className="rp-sc-arc" d={arc(r)} pathLength={1} />
            <path className={`rp-sc-arc-trail${i % 2 ? ' is-rev' : ''}`} d={arc(r)} pathLength={100} />
          </g>
        ))}
      </svg>
      {ORBIT.map((o) => (
        <div key={o.ring} className="rp-sc-ring" style={{ '--sw': `${o.ring % 2 ? 5 : -4}deg`, '--dur': `${9 + o.ring * 3}s` } as React.CSSProperties}>
          {o.nodes.map((n, j) => (
            <span key={n.name} className="rp-sc-node" style={{ ...pos(RINGS[o.ring], n.a), '--d': `${0.25 + o.ring * 0.18 + j * 0.08}s` } as React.CSSProperties} title={n.name}>
              <span className="rp-sc-node-face">
                <img src={L + n.logo} alt={n.name} loading="lazy" />
              </span>
            </span>
          ))}
        </div>
      ))}
      <span className="rp-sc-core" style={pos(0, 0)}>
        <i className="rp-sc-ripple" />
        <i className="rp-sc-ripple is-late" />
        <span className="rp-sc-core-face">
          <img src={EMBLEM} alt="Runport" />
        </span>
      </span>
    </div>
  )
}

// ---------- 2. guardrails: splits, ledger, plan approval ----------
const SPLITS = [
  { name: 'train.jsonl', role: 'fit' },
  { name: 'dev.jsonl', role: 'calibrate' },
  { name: 'test.jsonl', role: 'frozen', lock: true },
]
const LEDGER = [
  { id: 'case-041', basis: 'ESTIMATED', usd: '$0.0004' },
  { id: 'case-042', basis: 'ACTUAL', usd: '$0.0011' },
  { id: 'case-043', basis: 'UNAVAILABLE', usd: '—' },
  { id: 'case-044', basis: 'ESTIMATED', usd: '$0.0005' },
]

const ControlsArt: React.FC = () => {
  const s = useStage<HTMLDivElement>()
  return (
    <div ref={s.ref} className={`rp-sc-ctl${s.cls}`}>
      <div className="rp-sc-panel" style={{ '--d': '0.1s' } as React.CSSProperties}>
        <p className="rp-sc-panel-head">
          <Table2 size={13} aria-hidden="true" /> Splits
        </p>
        {SPLITS.map((r, i) => (
          <div key={r.name} className={`rp-sc-split${r.lock ? ' is-test' : ''}`} style={{ '--k': i } as React.CSSProperties}>
            <Table2 size={12} aria-hidden="true" />
            <span>{r.name}</span>
            <em>{r.lock ? <Lock size={10} aria-label="frozen" /> : r.role}</em>
          </div>
        ))}
      </div>

      <div className="rp-sc-panel" style={{ '--d': '0.22s' } as React.CSSProperties}>
        <p className="rp-sc-panel-head">
          <img src={`${L}sqlite.svg`} alt="" width={13} height={13} /> Spend ledger
        </p>
        <div className="rp-sc-ledger">
          <div className="rp-sc-ledger-track">
            {[...LEDGER, ...LEDGER].map((e, i) => (
              <div key={i} className="rp-sc-entry" aria-hidden={i >= LEDGER.length}>
                <span className="rp-sc-entry-meta">booked · {e.id}</span>
                <span className="rp-sc-entry-box">
                  <i className={`rp-sc-basis is-${e.basis.toLowerCase()}`}>{e.basis}</i>
                  <b className={e.usd === '—' ? 'is-null' : undefined}>{e.usd}</b>
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="rp-sc-panel" style={{ '--d': '0.34s' } as React.CSSProperties}>
        <p className="rp-sc-panel-head">
          <Fingerprint size={13} aria-hidden="true" /> Plan approval
        </p>
        <svg className="rp-sc-plan" viewBox="0 0 200 118" aria-hidden="true">
          <path className="rp-sc-branch" d="M 52 59 C 92 59, 96 26, 136 26" />
          <path className="rp-sc-branch" d="M 52 59 C 92 59, 96 92, 136 92" />
          <path className="rp-sc-branch-trail is-ok" d="M 52 59 C 92 59, 96 26, 136 26" pathLength={100} />
          <path className="rp-sc-branch-trail is-bad" d="M 52 59 C 92 59, 96 92, 136 92" pathLength={100} />
          <rect className="rp-sc-pnode" x="14" y="47" width="38" height="24" rx="6" />
          <text x="33" y="62.5" textAnchor="middle">plan</text>
          <text className="rp-sc-hash" x="33" y="86" textAnchor="middle">3f9a…c1e</text>
          <rect className="rp-sc-pnode is-ok" x="136" y="14" width="56" height="24" rx="6" />
          <text x="164" y="29.5" textAnchor="middle">approved</text>
          <rect className="rp-sc-pnode is-bad" x="136" y="80" width="56" height="24" rx="6" />
          <text x="164" y="95.5" textAnchor="middle">stale</text>
        </svg>
        <p className="rp-sc-plan-legend">
          <span>
            <Check size={10} aria-hidden="true" /> matches
          </span>
          <span>
            <X size={10} aria-hidden="true" /> rejected
          </span>
        </p>
      </div>
    </div>
  )
}

// ---------- 3. one command per step: rotating command list ----------
const COMMANDS = [
  { cmd: 'runport validate-dataset', note: 'schema · leakage' },
  { cmd: 'runport api-preflight', note: 'offline check' },
  { cmd: 'runport benchmark --replay', note: 'no network · $0.00' },
  { cmd: 'runport compare-runs', note: 'A ↔ B' },
  { cmd: 'runport budget status', note: 'caps · remaining' },
  { cmd: 'runport budget reconcile', note: 'clears UNRESOLVED' },
  { cmd: 'runport export-traces -f zip', note: 'sanitized' },
]
const STEP = 58

const CommandsArt: React.FC = () => {
  const s = useStage<HTMLDivElement>()
  const reduce = useReducedMotion()
  const [active, setActive] = useState(2)
  useEffect(() => {
    if (!s.live || reduce) return
    const t = window.setInterval(() => setActive((a) => (a + 1) % COMMANDS.length), 2400)
    return () => window.clearInterval(t)
  }, [s.live, reduce])
  const n = COMMANDS.length
  return (
    <div ref={s.ref} className={`rp-sc-cmds${s.cls}`}>
      {COMMANDS.map((c, i) => {
        let rel = (i - active + n) % n
        if (rel > n / 2) rel -= n
        const far = Math.abs(rel) > 2
        const on = rel === 0
        return (
          <motion.div
            key={c.cmd}
            className={`rp-sc-cmd${on ? ' is-on' : ''}`}
            aria-hidden={far}
            initial={false}
            animate={{
              y: Math.max(-3, Math.min(3, rel)) * STEP,
              x: on ? 28 : rel % 2 ? -8 : 8,
              opacity: far ? 0 : on ? 1 : Math.abs(rel) === 1 ? 0.5 : 0.16,
              scale: on ? 1 : 0.97,
            }}
            transition={reduce ? { duration: 0 } : { duration: 0.75, ease: EASE_OUT }}
          >
            <span className="rp-sc-cmd-icon">
              <Terminal size={13} aria-hidden="true" />
            </span>
            <code>{c.cmd}</code>
            <span className="rp-sc-cmd-note">{c.note}</span>
          </motion.div>
        )
      })}
    </div>
  )
}

// ---------- 4. local-first: everything inside your machine ----------
const LOCAL = [
  { logo: 'sqlite.svg', label: 'ledger' },
  { logo: 'ollama.svg', label: 'models' },
  { logo: 'python.svg', label: 'targets' },
]
const DOTS = [
  [12, 22], [86, 16], [22, 78], [78, 84], [50, 10], [93, 52], [6, 50], [64, 92], [36, 90], [70, 28], [30, 30], [92, 74],
]

const LocalArt: React.FC = () => {
  const s = useStage<HTMLDivElement>()
  return (
    <div ref={s.ref} className={`rp-sc-local${s.cls}`}>
      {DOTS.map(([x, y], i) => (
        <i key={i} className="rp-sc-dot" style={{ left: `${x}%`, top: `${y}%`, '--k': i } as React.CSSProperties} />
      ))}
      <div className="rp-sc-machine">
        <svg viewBox="0 0 320 190" preserveAspectRatio="none" aria-hidden="true">
          <rect className="rp-sc-frame" x="1" y="1" width="318" height="188" rx="22" pathLength={1} />
          <rect className="rp-sc-frame-march" x="1" y="1" width="318" height="188" rx="22" pathLength={100} />
        </svg>
        <span className="rp-sc-machine-label">your machine</span>
        <div className="rp-sc-local-row">
          {LOCAL.map((l, i) => (
            <span key={l.logo} className="rp-sc-local-item" style={{ '--k': i } as React.CSSProperties}>
              <span className="rp-sc-local-face">
                <img src={L + l.logo} alt="" />
              </span>
              <small>{l.label}</small>
            </span>
          ))}
        </div>
        <span className="rp-sc-offline">replay · offline · $0.00</span>
      </div>
    </div>
  )
}

const ART: Record<StackCard['key'], React.FC> = { stack: OrbitArt, controls: ControlsArt, cli: CommandsArt, local: LocalArt }

export const StackCards: React.FC = () => {
  const c = LANDING_CONTENT.stackCards
  return (
    <section className="rp-section rp-sc" id="built-for" aria-labelledby="rp-sc-title">
      <div className="rp-sc-inner">
        <Reveal className="rp-sc-head">
          <p className="rp-eyebrow">{c.eyebrow}</p>
          <h2 id="rp-sc-title" className="rp-h2 rp-fade-heading">
            {c.title}
          </h2>
          <p className="rp-body">{c.subheading}</p>
        </Reveal>
        <div className="rp-sc-grid">
          {c.cards.map((card, i) => {
            const Art = ART[card.key]
            return (
              <Reveal key={card.key} delay={(i % 2) * 0.08} className={`rp-sc-card rp-sc-card-${card.key}`}>
                <div className="rp-sc-art">
                  <Art />
                </div>
                <div className="rp-sc-copy">
                  <h3>{card.title}</h3>
                  <p>{card.body}</p>
                </div>
              </Reveal>
            )
          })}
        </div>
      </div>
    </section>
  )
}
