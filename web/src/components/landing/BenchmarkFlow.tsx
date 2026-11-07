import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useInView, useReducedMotion } from 'framer-motion'
import { Globe } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'
import { ECOSYSTEM, type EcoItem } from '../../data/ecosystem'
import { Reveal } from './motion'

// "Keep your stack. Runport benchmarks it."
//   integrations panel  ⇢  Runport  ⇢  sample run trace  ⇢  metric cards
// Dashed bracket lines join the stages; they are measured from the live layout.
// When the panel scrolls into view the sequence plays once: tiles light, the
// brackets carry the signal into Runport, the trace bars fill, and the metrics
// light one by one. Reduced motion shows the finished state. Each logo's tooltip
// says how Runport reaches it (data/ecosystem.ts); sample data is labelled.

const c = LANDING_CONTENT.stackFlow
const ITEMS = new Map(ECOSYSTEM.flatMap((g) => g.items).map((i) => [i.name, i]))
const item = (name: string): EcoItem => {
  const found = ITEMS.get(name)
  if (!found) throw new Error(`ecosystem entry missing: ${name}`)
  return found
}
const tip = (i: EcoItem) => (i.status === 'compat' ? `${i.name} · ${i.via}` : i.status === 'exp' ? `${i.name} · experimental connector` : `${i.name} · built-in connector`)

const COLUMNS: { label: string; cols: number; names: string[]; wide?: boolean }[] = [
  { label: 'Model providers', cols: 4, names: ['OpenAI', 'OpenRouter', 'Anthropic', 'Gemini', 'Mistral', 'DeepSeek', 'Groq', 'Together'] },
  { label: 'Workflows', cols: 2, names: ['Dify', 'LangGraph', 'LangChain', 'n8n'] },
  { label: 'Local & runtime', cols: 3, names: ['Ollama', 'vLLM', 'Python callable'], wide: true },
]
const SHORT: Record<string, string> = { 'Python callable': 'Python' }

const METRICS: { label: string; value: string; basis?: string; note?: string; key?: boolean }[] = [
  { label: 'Accuracy', value: '0.84', note: 'Wilson 95% 0.71–0.92', key: true },
  { label: 'p95 latency', value: '1.62s' },
  { label: 'Cost / 1k cases', value: '$0.82', basis: 'ESTIMATED' },
  { label: 'Invalid output', value: '4.0%' },
  { label: 'Agreement κ', value: '0.61', note: 'not accuracy' },
  { label: 'Unresolved spend', value: '$0.00' },
]

// 0 idle · 1 tiles · 2 top bracket · 3 runport · 4 line down · 5–10 trace rows · 11 bottom bracket · 12–17 metrics · 18 done
const DONE = 18
const stepMs = (s: number) => (s === 0 ? 120 : s === 1 ? 700 : s === 2 ? 700 : s === 3 ? 500 : s === 4 ? 450 : s < 11 ? 240 : s === 11 ? 450 : 170)
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

type Paths = { w: number; h: number; top: string[]; mid: string; bottom: string[] }
const seg = (x1: number, y1: number, x2: number, y2: number) => `M ${Math.round(x1)} ${Math.round(y1)} L ${Math.round(x2)} ${Math.round(y2)}`

const Handles: React.FC = () => (
  <>
    <i className="rp-cx-h is-tl" aria-hidden="true" />
    <i className="rp-cx-h is-tr" aria-hidden="true" />
    <i className="rp-cx-h is-bl" aria-hidden="true" />
    <i className="rp-cx-h is-br" aria-hidden="true" />
  </>
)

const Tile: React.FC<{ name: string; k: number }> = ({ name, k }) => {
  const i = item(name)
  return (
    <li className="rp-cx-tile" style={{ '--k': k } as React.CSSProperties} title={tip(i)}>
      {i.logo ? <img src={i.logo} alt="" loading="lazy" /> : <b>{i.mono}</b>}
      <span>{SHORT[name] ?? name}</span>
    </li>
  )
}

export const BenchmarkFlow: React.FC = () => {
  const reduce = useReducedMotion()
  const rootRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const emblemRef = useRef<HTMLDivElement>(null)
  const traceRef = useRef<HTMLDivElement>(null)
  const colRefs = useRef<(HTMLDivElement | null)[]>([])
  const metricRefs = useRef<(HTMLDivElement | null)[]>([])
  const started = useInView(panelRef, { once: true, margin: '0px 0px -25% 0px' })
  const live = useInView(rootRef, { margin: '-5% 0px -5% 0px' })
  const [s, setS] = useState(0)
  const [paths, setPaths] = useState<Paths | null>(null)

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

  const measure = useCallback(() => {
    const root = rootRef.current
    const P = panelRef.current?.getBoundingClientRect()
    const E = emblemRef.current?.getBoundingClientRect()
    const T = traceRef.current?.getBoundingClientRect()
    if (!root || !P || !E || !T) return
    const R = root.getBoundingClientRect()
    const x = (v: number) => v - R.left
    const y = (v: number) => v - R.top
    const ex = x(E.left + E.width / 2)
    const cols = colRefs.current.filter(Boolean).map((el) => (el as HTMLDivElement).getBoundingClientRect())
    const stacked = cols.length > 1 && cols[1].top > cols[0].top + 4
    const top: string[] = []
    if (stacked) {
      top.push(seg(ex, y(P.bottom), ex, y(E.top) - 6))
    } else {
      const yMid = y(P.bottom) + (E.top - P.bottom) * 0.45
      const cx = cols.map((r) => x(r.left + r.width / 2))
      cx.forEach((v) => top.push(seg(v, y(P.bottom), v, yMid)))
      top.push(seg(Math.min(...cx), yMid, Math.max(...cx), yMid))
      top.push(seg(ex, yMid, ex, y(E.top) - 6))
    }
    const mid = seg(ex, y(E.bottom) + 6, ex, y(T.top))
    const ms = metricRefs.current.filter(Boolean).map((el) => (el as HTMLDivElement).getBoundingClientRect())
    const bottom: string[] = []
    const oneRow = ms.length > 1 && ms.every((r) => Math.abs(r.top - ms[0].top) < 4)
    if (ms.length) {
      if (oneRow) {
        const yB = y(T.bottom) + (ms[0].top - T.bottom) * 0.5
        const mx = ms.map((r) => x(r.left + r.width / 2))
        bottom.push(seg(ex, y(T.bottom), ex, yB))
        bottom.push(seg(Math.min(...mx), yB, Math.max(...mx), yB))
        mx.forEach((v, i) => bottom.push(seg(v, yB, v, y(ms[i].top))))
      } else {
        bottom.push(seg(ex, y(T.bottom), ex, y(Math.min(...ms.map((r) => r.top)))))
      }
    }
    setPaths({ w: Math.round(R.width), h: Math.round(R.height), top, mid, bottom })
  }, [])

  useLayoutEffect(() => {
    measure()
    const ro = new ResizeObserver(measure)
    if (rootRef.current) ro.observe(rootRef.current)
    return () => ro.disconnect()
  }, [measure])

  const tiles = s >= 1
  const topOn = s >= 2
  const coreOn = s >= 3
  const midOn = s >= 4
  const rows = clamp(s - 4, 0, 6)
  const botOn = s >= 11
  const metrics = clamp(s - 11, 0, METRICS.length)
  const run = c.run

  let k = 0
  return (
    <div ref={rootRef} className={`rp-cx${live ? ' is-live' : ''}${reduce ? ' is-reduced' : ''}`}>
      {paths && (
        <svg className="rp-cx-lines" width={paths.w} height={paths.h} viewBox={`0 0 ${paths.w} ${paths.h}`} aria-hidden="true">
          {paths.top.map((d, i) => (
            <path key={`t${i}`} d={d} className={topOn ? 'is-on' : undefined} />
          ))}
          <path d={paths.mid} className={midOn ? 'is-on' : undefined} />
          {paths.bottom.map((d, i) => (
            <path key={`b${i}`} d={d} className={botOn ? 'is-on' : undefined} />
          ))}
        </svg>
      )}

      <div ref={panelRef} className={`rp-cx-panel${tiles ? ' is-on' : ''}`}>
        <Handles />
        {COLUMNS.map((col, ci) => (
          <div key={col.label} ref={(el) => (colRefs.current[ci] = el)} className="rp-cx-col" style={{ '--cols': col.cols } as React.CSSProperties}>
            <p className="rp-cx-label">{col.label}</p>
            <ul className="rp-cx-tiles">
              {col.names.map((n) => (
                <Tile key={n} name={n} k={k++} />
              ))}
              {col.wide && (
                <li className="rp-cx-tile is-wide" style={{ '--k': k++ } as React.CSSProperties} title="Any server that speaks the OpenAI API: vLLM, LM Studio, LocalAI, TGI, LiteLLM and more">
                  <Globe size={20} strokeWidth={1.6} aria-hidden="true" />
                  <span>Any OpenAI-compatible endpoint</span>
                </li>
              )}
            </ul>
          </div>
        ))}
      </div>

      <div ref={emblemRef} className={`rp-cx-core${coreOn ? ' is-on' : ''}`}>
        <img src="/assets/landing/runport-emblem.png" alt="Runport" />
      </div>

      <div ref={traceRef} className={`rp-cx-trace${midOn ? ' is-on' : ''}`}>
        <Handles />
        <div className="rp-cx-trace-head">
          <span>Sample run</span>
          <span className="rp-cx-accent">
            {run.total} cases · {run.elapsed}
          </span>
        </div>
        <div className="rp-cx-trace-body">
          <div className={`rp-cx-row is-root${rows > 0 ? ' is-on' : ''}`}>
            <i className="rp-cx-sq" />
            <span className="rp-cx-name">{run.id}</span>
            <span className="rp-cx-id">{c.compare.a.target} · {c.compare.a.via}</span>
            <span className="rp-cx-bar">
              <i style={{ left: '0%', width: '100%' }} />
            </span>
            <span className="rp-cx-ms">{run.elapsed}</span>
          </div>
          {run.rows.slice(0, 5).map((r, i) => (
            <div key={r.id} className={`rp-cx-row is-${r.status}${i + 1 < rows ? ' is-on' : ''}`} title={r.status.replace('_', ' ')}>
              <i className="rp-cx-sq" />
              <span className="rp-cx-name">{r.id}</span>
              <span className="rp-cx-id">{r.status.replace('_', ' ')}</span>
              <span className="rp-cx-bar">
                <i style={{ left: `${i * 14}%`, width: `${(r.ms / 2000) * 30}%` }} />
              </span>
              <span className="rp-cx-ms">{r.ms >= 1000 ? `${(r.ms / 1000).toFixed(2)}s` : `${r.ms}ms`}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="rp-cx-metrics">
        {METRICS.map((m, i) => (
          <div key={m.label} ref={(el) => (metricRefs.current[i] = el)} className={`rp-cx-metric${i < metrics ? ' is-on' : ''}${m.key ? ' is-key' : ''}`}>
            <span className="rp-cx-metric-label">{m.label}</span>
            <span className="rp-cx-metric-value">
              {m.basis && <i className="rp-cx-basis">{m.basis}</i>}
              {m.value}
            </span>
            {m.note && <span className="rp-cx-metric-note">{m.note}</span>}
          </div>
        ))}
      </div>

      <p className="rp-cx-foot">Sample run for illustration. Hover a logo to see how Runport reaches it.</p>
    </div>
  )
}

/** The landing section: heading, then the integration flow. */
export const BenchmarkFlowSection: React.FC = () => (
  <section className="rp-section rp-sf" id="stack" aria-labelledby="rp-sf-title">
    <div className="rp-sf-head">
      <Reveal>
        <p className="rp-eyebrow">Integrations</p>
        <h2 id="rp-sf-title" className="rp-h2 rp-fade-heading">
          {c.titleA}
          <br />
          {c.titleB}
        </h2>
      </Reveal>
      <Reveal delay={0.08}>
        <p className="rp-body">{c.description}</p>
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
