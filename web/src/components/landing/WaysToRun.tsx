import React, { useState } from 'react'
import { motion, useReducedMotion, type Variants } from 'framer-motion'
import { ArrowUpRight, Check, Copy } from 'lucide-react'
import { LANDING_CONTENT, type WayItem } from '../../data/landingContent'
import { EASE_OUT, Reveal, ScaledCanvas } from './motion'
import { MOCKUP_SIZE, RunportMockup } from './RunportMockups'

// Three ways to run Runport locally. Each card is a painting with a live
// window on top: the CLI types its output, the terminal UI fills its gauges,
// and the web dashboard window rises into place when the card scrolls in.

const IN_VIEW = { once: true, margin: '0px 0px -18% 0px' } as const

const Dots: React.FC = () => (
  <span className="rp-way-dots" aria-hidden="true">
    <i />
    <i />
    <i />
  </span>
)

// ---------- command line ----------
const CLI_LINES: { t: string; tone?: 'cmd' | 'ok' | 'dim' }[] = [
  { t: '$ uv run runport validate-dataset', tone: 'cmd' },
  { t: '  TRAIN 2 · DEV 2 · TEST 2', tone: 'dim' },
  { t: '✓ Dataset validation passed', tone: 'ok' },
  { t: '  6 cases · zero leakage detected', tone: 'dim' },
  { t: '$ uv run runport benchmark --replay', tone: 'cmd' },
  { t: '✓ Run stored · provenance REPLAYED', tone: 'ok' },
  { t: '  spend $0.00 · no network calls', tone: 'dim' },
  { t: '$ uv run runport budget status', tone: 'cmd' },
  { t: '  total $5.00 · spent $0.00 · left $5.00', tone: 'dim' },
]

const CliWindow: React.FC = () => {
  const reduce = useReducedMotion()
  const list: Variants = { hidden: {}, show: { transition: { staggerChildren: reduce ? 0 : 0.32, delayChildren: reduce ? 0 : 0.35 } } }
  const line: Variants = {
    hidden: reduce ? { opacity: 1 } : { opacity: 0, x: -6 },
    show: { opacity: 1, x: 0, transition: { duration: 0.35, ease: EASE_OUT } },
  }
  return (
    <div className="rp-way-win rp-way-term">
      <div className="rp-way-bar">
        <Dots />
        <span>runport — zsh</span>
      </div>
      <motion.div className="rp-way-term-body" initial="hidden" whileInView="show" viewport={IN_VIEW} variants={list}>
        {CLI_LINES.map((l, i) => (
          <motion.p key={i} variants={line} className={l.tone ? `is-${l.tone}` : undefined}>
            {l.t}
          </motion.p>
        ))}
        <motion.p variants={line} className="is-cmd">
          $ <span className="rp-way-caret" aria-hidden="true" />
        </motion.p>
      </motion.div>
    </div>
  )
}

// ---------- terminal UI ----------
const GAUGES = [
  { label: 'Total', cap: '$5.00', used: 0.18 },
  { label: 'Pilot', cap: '$1.00', used: 0.42 },
  { label: 'Per run', cap: '$1.00', used: 0.06 },
]
const ROSTER = [
  { id: 'google/gemini-3.5-flash-lite', state: 'READY' },
  { id: 'openai/gpt-4.1-nano', state: 'READY' },
  { id: 'local/llama3.1 (ollama)', state: '$0.00' },
]

const TuiWindow: React.FC = () => {
  const reduce = useReducedMotion()
  return (
    <div className="rp-way-win rp-way-term rp-way-tui">
      <div className="rp-way-bar">
        <Dots />
        <span>runport ui</span>
      </div>
      <div className="rp-way-tui-body">
        <div className="rp-way-tui-head">
          <span>RUNPORT</span>
          <span className="is-dim">local WAL · 0 unresolved</span>
        </div>
        <div className="rp-way-box">
          <p className="rp-way-box-title">Budget ceilings</p>
          {GAUGES.map((g, i) => (
            <div key={g.label} className="rp-way-gauge">
              <span>{g.label}</span>
              <span className="rp-way-gauge-track">
                <motion.span
                  className="rp-way-gauge-fill"
                  initial={{ scaleX: reduce ? g.used : 0 }}
                  whileInView={{ scaleX: g.used }}
                  viewport={IN_VIEW}
                  transition={{ duration: reduce ? 0 : 1.1, delay: reduce ? 0 : 0.4 + i * 0.18, ease: EASE_OUT }}
                />
              </span>
              <span className="is-dim">{g.cap}</span>
            </div>
          ))}
        </div>
        <div className="rp-way-box">
          <p className="rp-way-box-title">Model roster</p>
          {ROSTER.map((r, i) => (
            <motion.div
              key={r.id}
              className="rp-way-roster"
              initial={reduce ? { opacity: 1 } : { opacity: 0 }}
              whileInView={{ opacity: 1 }}
              viewport={IN_VIEW}
              transition={{ duration: 0.4, delay: reduce ? 0 : 1 + i * 0.2 }}
            >
              <span>{r.id}</span>
              <span className="is-ok">{r.state}</span>
            </motion.div>
          ))}
        </div>
        <p className="rp-way-tui-foot is-dim">q quit · r refresh · b budget · m models</p>
      </div>
    </div>
  )
}

// ---------- web dashboard ----------
const WebWindow: React.FC = () => {
  const reduce = useReducedMotion()
  return (
    <motion.div
      className="rp-way-win rp-way-browser"
      initial={reduce ? { opacity: 1 } : { opacity: 0, y: 36 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={IN_VIEW}
      transition={{ duration: reduce ? 0 : 0.9, delay: reduce ? 0 : 0.25, ease: EASE_OUT }}
    >
      <div className="rp-way-bar">
        <Dots />
        <span className="rp-way-url">127.0.0.1:8000</span>
      </div>
      <ScaledCanvas width={MOCKUP_SIZE.width} height={MOCKUP_SIZE.height} className="rp-way-canvas">
        <RunportMockup kind="compare" />
      </ScaledCanvas>
    </motion.div>
  )
}

const WINDOWS: Record<WayItem['kind'], React.FC> = { cli: CliWindow, tui: TuiWindow, web: WebWindow }

const CopyChip: React.FC<{ text: string }> = ({ text }) => {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable: the command stays selectable */
    }
  }
  return (
    <button type="button" className="rp-way-copy" onClick={copy} aria-label={copied ? 'Copied' : `Copy ${text}`}>
      <code>{text}</code>
      {copied ? <Check size={16} /> : <Copy size={16} />}
    </button>
  )
}

const newTab = (href: string) => (/^https?:/.test(href) ? { target: '_blank', rel: 'noopener noreferrer' } : {})

export const WaysToRun: React.FC = () => {
  const c = LANDING_CONTENT.waysToRun
  return (
    <section className="rp-section rp-ways" id="ways" aria-labelledby="rp-ways-title">
      <div className="rp-ways-inner">
        <Reveal className="rp-ways-head">
          <p className="rp-eyebrow">Interfaces</p>
          <h2 id="rp-ways-title" className="rp-h2 rp-fade-heading">
            {c.titleA} {c.titleB}
          </h2>
          <p className="rp-body">{c.subheading}</p>
        </Reveal>
        <div className="rp-ways-grid">
          {c.items.map((item, i) => {
            const Win = WINDOWS[item.kind]
            return (
              <Reveal key={item.kind} delay={i * 0.1} className="rp-way">
                <div className={`rp-way-media rp-way-media-${item.kind}`}>
                  <img className="rp-way-art" src={item.image} alt="" loading="lazy" />
                  <Win />
                </div>
                <h3 className="rp-way-title">{item.title}</h3>
                <p className="rp-way-body">{item.body}</p>
                <div className="rp-way-action">
                  {item.action.type === 'copy' ? (
                    <CopyChip text={item.action.text} />
                  ) : (
                    <a className="rp-way-btn" href={item.action.href} {...newTab(item.action.href)}>
                      {item.action.label}
                      <ArrowUpRight size={18} aria-hidden="true" />
                    </a>
                  )}
                </div>
              </Reveal>
            )
          })}
        </div>
      </div>
    </section>
  )
}
