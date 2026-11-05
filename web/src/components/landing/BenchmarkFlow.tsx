import React, { useEffect, useRef, useState } from 'react'
import { useInView, useReducedMotion } from 'framer-motion'
import { Braces, Download, FileJson, Gavel, Globe, Puzzle, Regex, RotateCcw, Search, Target, Terminal, Type, type LucideIcon } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'
import { ECOSYSTEM, type EcoGroup, type EcoItem } from '../../data/ecosystem'
import { Reveal } from './motion'

// "Keep your stack. Runport benchmarks it." as three connected layers:
//   01 Connect  — the ecosystem, one row of overlapping logos per category
//   02 Execute  — the Runport engine and its guarded lifecycle
//   03 Compare  — a compact sample-run preview
// One spine joins the layers. A step counter plays the sample run once when the
// engine scrolls into view; afterwards an occasional ping lights one category and
// sends a signal down the spine while the section is on screen. Reduced motion
// shows the finished state. Routes per logo live in data/ecosystem.ts (tooltips).

const c = LANDING_CONTENT.stackFlow

const ICONS: Record<NonNullable<EcoItem['icon']>, LucideIcon> = {
  globe: Globe,
  terminal: Terminal,
  replay: RotateCcw,
  puzzle: Puzzle,
  target: Target,
  regex: Regex,
  braces: Braces,
  text: Type,
  search: Search,
  gavel: Gavel,
  database: FileJson,
  file: FileJson,
  download: Download,
  upload: Download,
}
const tip = (i: EcoItem) => (i.status === 'compat' ? `${i.name} · ${i.via}` : i.status === 'exp' ? `${i.name} · experimental connector` : `${i.name} · built-in`)
const MAX_DISCS = 6

// step sequence: 0 idle · 1 signal in · 2 engine on · 3–11 stages · 12 signal out · 13–18 rows · 19–22 metrics · 23 done
const DONE = 23
const stepMs = (s: number) => (s === 0 ? 150 : s === 1 ? 800 : s === 2 ? 300 : s < 12 ? 300 : s === 12 ? 650 : s < 19 ? 230 : 180)
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

// ---------- layer chrome ----------
const LayerHead: React.FC<{ num: string; title: string; body: string; aside?: React.ReactNode }> = ({ num, title, body, aside }) => (
  <header className="rp-ly-head">
    <span className="rp-ly-num">{num}</span>
    <h3>{title}</h3>
    <p>{body}</p>
    {aside}
  </header>
)

const Spine: React.FC<{ flowKey: string | null; lit: boolean; delay?: number }> = ({ flowKey, lit, delay = 0 }) => (
  <div className={`rp-ly-spine${lit ? ' is-lit' : ''}`} aria-hidden="true">
    <i className="rp-ly-port" />
    <svg viewBox="0 0 2 100" preserveAspectRatio="none">
      <line className="rp-ly-spine-base" x1="1" y1="0" x2="1" y2="100" />
      {flowKey && <line key={flowKey} className="rp-ly-spine-trail" x1="1" y1="0" x2="1" y2="100" pathLength={100} style={{ animationDelay: `${delay}s` }} />}
    </svg>
    <i className="rp-ly-port" />
  </div>
)

// ---------- 01 connect ----------
const Disc: React.FC<{ item: EcoItem; k: number }> = ({ item, k }) => {
  const Icon = item.icon ? ICONS[item.icon] : null
  return (
    <span className="rp-ly-disc" style={{ '--k': k } as React.CSSProperties} title={tip(item)}>
      {item.logo ? <img src={item.logo} alt={item.name} loading="lazy" /> : Icon ? <Icon size={15} strokeWidth={1.7} aria-label={item.name} /> : <b aria-label={item.name}>{item.mono}</b>}
    </span>
  )
}

const names = (g: EcoGroup) => {
  const n = g.items.map((i) => i.name)
  return n.length <= 2 ? n.join(' and ') : `${n.slice(0, 2).join(', ')} and ${n.length - 2} more`
}

const Category: React.FC<{ group: EcoGroup; ci: number; hot: boolean }> = ({ group, ci, hot }) => {
  const shown = group.items.slice(0, MAX_DISCS)
  const extra = group.items.length - shown.length
  return (
    <div className={`rp-ly-cat${hot ? ' is-hot' : ''}`} style={{ '--ci': ci } as React.CSSProperties}>
      <p className="rp-ly-cat-name">{group.label}</p>
      <div className="rp-ly-discs">
        {shown.map((it, k) => (
          <Disc key={it.name} item={it} k={k} />
        ))}
        {extra > 0 && (
          <span className="rp-ly-disc is-more" style={{ '--k': shown.length } as React.CSSProperties} title={group.items.slice(MAX_DISCS).map((i) => i.name).join(', ')}>
            +{extra}
          </span>
        )}
      </div>
      <p className="rp-ly-cat-list" title={group.items.map((i) => i.name).join(', ')}>
        {names(group)}
      </p>
    </div>
  )
}

// ---------- 02 execute ----------
const Lifecycle: React.FC<{ lit: number; done: boolean; pingKey: number }> = ({ lit, done, pingKey }) => {
  const stages = c.stages
  return (
    <div className="rp-ly-life">
      <div className="rp-ly-guards">
        <span>7 runner guards · fail closed</span>
      </div>
      <div className="rp-ly-track" aria-hidden="true">
        <i className="rp-ly-track-fill" style={{ transform: `scaleX(${clamp((lit - 1) / (stages.length - 1), 0, 1)})` }} />
        {pingKey > 0 && <i key={pingKey} className="rp-ly-sweep" />}
      </div>
      <ol className="rp-ly-stages">
        {stages.map((s, i) => (
          <li key={s.key} className={`rp-ly-stage${i < lit ? ' is-lit' : ''}${i === lit - 1 && !done ? ' is-now' : ''}`}>
            <span className="rp-ly-node" />
            <span>{s.label}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

// ---------- 03 compare ----------
const fmtMs = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`)

const Preview: React.FC<{ rows: number; metrics: number }> = ({ rows, metrics }) => {
  const cmp = c.compare
  const done = Math.round((rows / c.run.rows.length) * c.run.total)
  return (
    <div className="rp-ly-win">
      <div className="rp-ly-win-bar">
        <span className="rp-ly-sample">Sample run</span>
        <span className="rp-ly-mono">{c.run.id}</span>
        <span className="rp-ly-prog">
          <i style={{ transform: `scaleX(${done / c.run.total})` }} />
        </span>
        <span className="rp-ly-mono">
          {done}/{c.run.total}
        </span>
      </div>
      <div className="rp-ly-res">
        <div className="rp-ly-cases">
          {c.run.rows.map((r, i) => (
            <div key={r.id} className={`rp-ly-case is-${r.status}${i < rows ? ' is-on' : ''}`} title={r.status.replace('_', ' ')}>
              <i className="rp-ly-dot" />
              <span className="rp-ly-mono">{r.id}</span>
              <span className="rp-ly-lane">
                <i style={{ left: `${i * 12}%`, width: `${(r.ms / 2000) * 40}%` }} />
              </span>
              <span className="rp-ly-mono rp-ly-dim">{fmtMs(r.ms)}</span>
            </div>
          ))}
        </div>
        <table className="rp-ly-cmp">
          <thead>
            <tr>
              <th />
              <th>
                <small>Run A</small>
                {cmp.a.target}
              </th>
              <th>
                <small>Run B</small>
                {cmp.b.target}
              </th>
            </tr>
          </thead>
          <tbody>
            {cmp.primary.map((m, i) => (
              <tr key={m.label} className={i < metrics ? 'is-on' : undefined}>
                <th scope="row">{m.label}</th>
                <td>
                  {m.aBasis && <i className={`rp-ly-basis is-${m.aBasis.toLowerCase()}`}>{m.aBasis}</i>}
                  <b className={m.a === null ? 'is-null' : undefined}>{m.a ?? '—'}</b>
                </td>
                <td>
                  {m.bBasis && <i className={`rp-ly-basis is-${m.bBasis.toLowerCase()}`}>{m.bBasis}</i>}
                  <b className={m.b === null ? 'is-null' : undefined}>{m.b ?? '—'}</b>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={`rp-ly-kappa${metrics >= cmp.primary.length ? ' is-on' : ''}`}>
        Agreement κ {cmp.secondary[1].value} between runs · model consensus, not accuracy
      </p>
    </div>
  )
}

// ---------- composition ----------
export const BenchmarkFlow: React.FC = () => {
  const reduce = useReducedMotion()
  const rootRef = useRef<HTMLDivElement>(null)
  const ecoRef = useRef<HTMLDivElement>(null)
  const engineRef = useRef<HTMLDivElement>(null)
  const ecoSeen = useInView(ecoRef, { once: true, margin: '0px 0px -12% 0px' })
  const started = useInView(engineRef, { once: true, margin: '0px 0px -25% 0px' })
  const live = useInView(rootRef, { margin: '-10% 0px -10% 0px' })
  const [s, setS] = useState(0)
  const [ping, setPing] = useState<{ g: number | null; k: number }>({ g: null, k: 0 })

  useEffect(() => {
    if (!started) return
    if (reduce) {
      setS(DONE)
      return
    }
    if (s >= DONE) return
    const t = window.setTimeout(() => setS(s + 1), stepMs(s))
    return () => window.clearTimeout(t)
  }, [started, s, reduce])

  const done = s >= DONE
  useEffect(() => {
    if (!done || !live || reduce) return
    const t = window.setInterval(() => setPing((p) => ({ g: (p.g === null ? 0 : p.g + 1) % ECOSYSTEM.length, k: p.k + 1 })), 3400)
    return () => window.clearInterval(t)
  }, [done, live, reduce])

  const lit = clamp(s - 2, 0, c.stages.length)
  const rows = clamp(s - 12, 0, c.run.rows.length)
  const metrics = clamp(s - 18, 0, c.compare.primary.length)
  const inKey = ping.k > 0 ? `p${ping.k}` : s >= 1 && !reduce ? 'seq' : null
  const outKey = ping.k > 0 ? `p${ping.k}` : s >= 12 && !reduce ? 'seq' : null

  return (
    <div ref={rootRef} className={`rp-ly${reduce ? ' is-reduced' : ''}`}>
      <section ref={ecoRef} className={`rp-ly-layer rp-ly-connect${ecoSeen || reduce ? ' is-in' : ''}`} aria-label="Connect">
        <LayerHead num="01" title="Connect" body="Hosted APIs, local servers, workflow platforms and your own code, all behind one target interface." />
        <div className="rp-ly-cats">
          {ECOSYSTEM.map((g, i) => (
            <Category key={g.key} group={g} ci={i} hot={ping.g === i} />
          ))}
        </div>
      </section>

      <Spine flowKey={inKey} lit={s >= 1} />

      <section ref={engineRef} className={`rp-ly-layer rp-ly-engine${s >= 2 ? ' is-on' : ''}${done ? ' is-done' : ''}`} aria-label="Execute">
        <span className="rp-ly-ring" aria-hidden="true" />
        {ping.k > 0 && <span key={ping.k} className="rp-ly-glow" aria-hidden="true" />}
        <LayerHead
          num="02"
          title="Execute"
          body="Every call runs the same guarded lifecycle. Anything unapproved or over budget fails closed."
          aside={
            <span className={`rp-ly-state${done ? ' is-done' : s >= 2 ? ' is-run' : ''}`}>
              <img src="/assets/landing/runport-emblem.png" alt="" />
              {done ? 'Run complete' : s >= 2 ? 'Executing' : 'Ready'}
            </span>
          }
        />
        <Lifecycle lit={lit} done={done} pingKey={ping.k} />
      </section>

      <Spine flowKey={outKey} lit={s >= 12} delay={ping.k > 0 ? 1 : 0} />

      <section className={`rp-ly-layer rp-ly-compare${s >= 12 ? ' is-on' : ''}`} aria-label="Compare">
        <LayerHead num="03" title="Compare" body="Per-case traces roll up into accuracy with confidence intervals, latency, and cost with its source." />
        <Preview rows={rows} metrics={metrics} />
      </section>

      <p className="rp-ly-foot">Results shown are a sample run for illustration. Hover a logo to see how Runport reaches it.</p>
    </div>
  )
}

/** The landing section: heading, then the three connected layers. */
export const BenchmarkFlowSection: React.FC = () => (
  <section className="rp-section rp-sf" id="stack" aria-labelledby="rp-sf-title">
    <div className="rp-sf-head">
      <Reveal>
        <p className="rp-eyebrow">Integrations</p>
        <h2 id="rp-sf-title" className="rp-sf-title">
          {c.titleA}
          <br />
          {c.titleB}
        </h2>
      </Reveal>
      <Reveal delay={0.08}>
        <p className="rp-sf-sub">{c.description}</p>
      </Reveal>
      <Reveal delay={0.14}>
        <a className="rp-pill rp-pill-sm rp-pill-glass rp-sf-cta" href={c.ctaHref} target="_blank" rel="noopener noreferrer">
          {c.cta} <span aria-hidden="true">↗</span>
        </a>
      </Reveal>
    </div>
    <BenchmarkFlow />
  </section>
)
