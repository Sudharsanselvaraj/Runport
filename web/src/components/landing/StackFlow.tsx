import React, { useRef } from 'react'
import { motion, useMotionValue, useReducedMotion, useScroll, useTransform, type MotionValue } from 'framer-motion'
import { Globe, Puzzle, RotateCcw, Terminal } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'
import { Reveal } from './motion'

// Each stage has its own scroll progress (0 → 1 as that block rises into view),
// so every part animates while it is on screen, in order: targets light up, the connector draws into the
// Runport mark, the seven guards fire in sequence, the trace waterfall grows,
// and the scorecard fills. Scrolling back reverses it. Reduced motion shows the
// finished state.

type P = MotionValue<number>

// Neutral palette: idle elements sit at low contrast, lit ones step up to white.
const IDLE_LINE = 'rgba(255, 255, 255, 0.08)'
const LIT_LINE = 'rgba(255, 255, 255, 0.24)'
const ICONS = { globe: Globe, terminal: Terminal, puzzle: Puzzle, replay: RotateCcw }

/** 0 → 1 across [a, b] of the section progress. */
const useStage = (p: P, a: number, b: number) => useTransform(p, [a, b], [0, 1], { clamp: true })

interface TileSpec {
  name: string
  logo?: string
  icon?: keyof typeof ICONS
  exp?: boolean
}

const Tile: React.FC<{ p: P; at: number; tile: TileSpec }> = ({ p, at, tile }) => {
  const { name, logo, icon, exp } = tile
  const s = useStage(p, at, at + 0.25)
  const borderColor = useTransform(s, [0, 1], [IDLE_LINE, LIT_LINE])
  const backgroundColor = useTransform(s, [0, 1], ['rgba(255,255,255,0.015)', 'rgba(255,255,255,0.05)'])
  const opacity = useTransform(s, [0, 1], [0.4, 1])
  const filter = useTransform(s, (v) => `grayscale(${1 - v})`)
  const Icon = icon ? ICONS[icon] : null
  return (
    <motion.div className="rp-sf-tile" style={{ borderColor, backgroundColor }}>
      <motion.span className="rp-sf-logo" style={{ opacity, filter }}>
        {logo ? <img src={logo} alt="" loading="lazy" /> : Icon ? <Icon size={18} strokeWidth={1.6} /> : null}
      </motion.span>
      <motion.span className="rp-sf-name" style={{ opacity }}>{name}</motion.span>
      {exp && <span className="rp-sf-exp" title="Experimental connector">exp</span>}
    </motion.div>
  )
}

/** A connector drawn top → bottom by clipping, so the dash pattern never shifts. */
const Wire: React.FC<{ p: P; a: number; b: number; d: string; className?: string; height: number }> = ({ p, a, b, d, className, height }) => {
  const s = useStage(p, a, b)
  const clipPath = useTransform(s, (v) => `inset(0 0 ${(1 - v) * 100}% 0)`)
  return (
    <div className={`rp-sf-wire ${className ?? ''}`} style={{ height }} aria-hidden="true">
      <svg viewBox={`0 0 1000 ${height}`} preserveAspectRatio="none">
        <path d={d} className="rp-sf-wire-idle" vectorEffect="non-scaling-stroke" />
      </svg>
      <motion.svg viewBox={`0 0 1000 ${height}`} preserveAspectRatio="none" style={{ clipPath }}>
        <path d={d} className="rp-sf-wire-lit" vectorEffect="non-scaling-stroke" />
      </motion.svg>
    </div>
  )
}

const Guard: React.FC<{ p: P; at: number; label: string }> = ({ p, at, label }) => {
  const s = useStage(p, at, at + 0.08)
  const borderColor = useTransform(s, [0, 1], [IDLE_LINE, LIT_LINE])
  const color = useTransform(s, [0, 1], ['rgba(255,255,255,0.4)', 'rgba(255,255,255,1)'])
  return (
    <motion.li className="rp-sf-guard" style={{ borderColor, color }}>
      {label}
    </motion.li>
  )
}

interface Row {
  id: string
  status: string
  ms: number
  basis: string
  flag?: boolean
}

const TraceRow: React.FC<{ p: P; at: number; row: Row; left: number; width: number }> = ({ p, at, row, left, width }) => {
  const s = useStage(p, at, at + 0.2)
  const scaleX = s
  const opacity = useTransform(s, [0, 0.15, 1], [0.35, 1, 1])
  return (
    <motion.div className={`rp-sf-row${row.flag ? ' is-flag' : ''}`} style={{ opacity }}>
      <span className="rp-sf-row-node" aria-hidden="true" />
      <span className="rp-sf-row-id">{row.id}</span>
      <span className="rp-sf-row-status">{row.status}</span>
      <span className="rp-sf-row-track">
        <motion.span className="rp-sf-row-bar" style={{ left: `${left}%`, width: `${width}%`, scaleX }} />
      </span>
      <span className="rp-sf-row-ms">{row.ms >= 1000 ? `${(row.ms / 1000).toFixed(2)}s` : `${row.ms}ms`}</span>
      <span className="rp-sf-row-basis">{row.basis}</span>
    </motion.div>
  )
}

interface Score {
  label: string
  value: number
  decimals: number
  prefix?: string
  suffix?: string
  note: string
  flag?: boolean
}

const ScoreCard: React.FC<{ p: P; at: number; score: Score }> = ({ p, at, score }) => {
  const s = useStage(p, at, at + 0.35)
  const text = useTransform(s, (v) => `${score.prefix ?? ''}${(score.value * v).toFixed(score.decimals)}${score.suffix ?? ''}`)
  const borderColor = useTransform(s, [0, 1], [IDLE_LINE, score.flag ? 'rgba(255,255,255,0.32)' : 'rgba(255,255,255,0.12)'])
  const backgroundColor = useTransform(s, [0, 1], ['rgba(255,255,255,0.01)', score.flag ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.025)'])
  const opacity = useTransform(s, [0, 1], [0.4, 1])
  return (
    <motion.div className={`rp-sf-score${score.flag ? ' is-flag' : ''}`} style={{ borderColor, backgroundColor, opacity }}>
      <span className="rp-sf-score-label">{score.label}</span>
      <motion.span className="rp-sf-score-value" aria-label={`${score.prefix ?? ''}${score.value.toFixed(score.decimals)}${score.suffix ?? ''}`}>
        {text}
      </motion.span>
      <span className="rp-sf-score-note">{score.note}</span>
    </motion.div>
  )
}

export const StackFlow: React.FC = () => {
  const c = LANDING_CONTENT.stackFlow
  const targetsRef = useRef<HTMLDivElement>(null)
  const coreRef = useRef<HTMLDivElement>(null)
  const traceRef = useRef<HTMLDivElement>(null)
  const scoresRef = useRef<HTMLDivElement>(null)
  const reduce = useReducedMotion()
  const done = useMotionValue(1)
  const a = useScroll({ target: targetsRef, offset: ['start 92%', 'center 55%'] }).scrollYProgress
  const b = useScroll({ target: coreRef, offset: ['start 100%', 'end 62%'] }).scrollYProgress
  const t = useScroll({ target: traceRef, offset: ['start 98%', 'end 72%'] }).scrollYProgress
  const d = useScroll({ target: scoresRef, offset: ['start 108%', 'end 82%'] }).scrollYProgress
  const pTargets: P = reduce ? done : a
  const pCore: P = reduce ? done : b
  const pTrace: P = reduce ? done : t
  const pScores: P = reduce ? done : d

  // emblem: glows once the targets have connected
  const glow = useStage(pCore, 0.22, 0.42)
  const markFilter = useTransform(glow, (v) => `drop-shadow(0 0 ${v * 24}px rgba(255,255,255,${v * 0.28}))`)
  const markOpacity = useTransform(glow, [0, 1], [0.35, 1])

  // timeline layout for the trace waterfall
  const total = c.trace.rows.reduce((n, r) => n + r.ms, 0)
  let cursor = 0
  const bars = c.trace.rows.map((r) => {
    const left = (cursor / total) * 100
    cursor += r.ms
    return { left, width: (r.ms / total) * 100 }
  })

  const tileCount = c.groups.reduce((n, g) => n + g.tiles.length, 0)
  let tileIndex = 0

  return (
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

      <div className="rp-sf-diagram">
        {/* 1. targets */}
        <div className="rp-sf-panel rp-sf-targets" ref={targetsRef}>
          {c.groups.map((g) => (
            <div key={g.label} className="rp-sf-group" style={{ ['--cols' as string]: g.cols, flexGrow: g.cols }}>
              <p className="rp-sf-label">{g.label}</p>
              <div className="rp-sf-tiles">
                {g.tiles.map((t) => {
                  const at = (tileIndex++ / tileCount) * 0.75
                  return <Tile key={t.name} p={pTargets} at={at} tile={t} />
                })}
              </div>
            </div>
          ))}
        </div>

        {/* group centres: 2/7, 3/7, 2/7 of the width → 14.3 %, 50 %, 85.7 % */}
        <Wire p={pCore} a={0} b={0.25} height={64} className="rp-sf-wire-merge" d="M143 0 V32 H857 V0 M500 32 V64" />
        <Wire p={pCore} a={0} b={0.25} height={40} className="rp-sf-wire-single" d="M500 0 V40" />

        {/* 2. Runport and its guard order */}
        <div className="rp-sf-core" ref={coreRef}>
          <motion.img
            className="rp-sf-mark"
            src="/assets/landing/runport-emblem.png"
            alt="Runport"
            style={{ filter: markFilter, opacity: markOpacity }}
          />
          <ol className="rp-sf-guards" aria-label="Runner guard order">
            {c.guards.map((g, i) => (
              <Guard key={g} p={pCore} at={0.38 + i * 0.08} label={g} />
            ))}
          </ol>
        </div>

        <Wire p={pTrace} a={0} b={0.15} height={40} d="M500 0 V40" />

        {/* 3. run trace */}
        <div className="rp-sf-panel rp-sf-trace" ref={traceRef}>
          <div className="rp-sf-trace-head">
            <p className="rp-sf-label">{c.trace.title}</p>
            <p className="rp-sf-label rp-sf-trace-meta">
              {c.trace.meta} <span>· {c.trace.total}</span>
            </p>
          </div>
          <div className="rp-sf-rows">
            {c.trace.rows.map((r, i) => (
              <TraceRow key={r.id} p={pTrace} at={0.15 + i * 0.15} row={r} left={bars[i].left} width={bars[i].width} />
            ))}
          </div>
        </div>

        <Wire
          p={pScores}
          a={0}
          b={0.3}
          height={56}
          className="rp-sf-wire-fan"
          d="M500 0 V28 M83 56 V28 H917 V56 M250 28 V56 M417 28 V56 M583 28 V56 M750 28 V56"
        />
        <Wire p={pScores} a={0} b={0.3} height={40} className="rp-sf-wire-single" d="M500 0 V40" />

        {/* 4. scorecard */}
        <div className="rp-sf-scores" ref={scoresRef}>
          {c.scores.map((s, i) => (
            <ScoreCard key={s.label} p={pScores} at={0.28 + i * 0.07} score={s} />
          ))}
        </div>
        <p className="rp-sf-footnote">Sample run for illustration. Scores are computed against human-approved labels; agreement is reported separately.</p>
      </div>
    </section>
  )
}
