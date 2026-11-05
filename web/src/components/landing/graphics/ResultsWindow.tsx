import React, { useRef } from 'react'
import { useInView, useReducedMotion } from 'framer-motion'
import {
  AGREEMENT,
  CLASSES,
  CONFUSION,
  LEDGER,
  PLAN,
  RESULTS,
  costPer1kCell,
  formatAmount,
  pct,
  perClassRecall,
  unresolvedCount,
  wilson,
} from '../../../data/sampleRun'
import { SampleChip } from '../SampleChip'

// Card 4 (wide): a cropped results window built in React/CSS. When it scrolls
// into view the scorecards, the confusion matrix and the per-class bars reveal
// in sequence (CSS transitions with staggered delays, once). The window fades
// into the card at the bottom. Reduced motion shows everything at once.

const A = AGREEMENT.a
const r = RESULTS[A]
const [lo, hi] = wilson(r.correct, PLAN.cases)
const cost = costPer1kCell(A)
const unresolved = unresolvedCount(LEDGER)
const recall = perClassRecall()
const maxCell = Math.max(...CONFUSION.flat())

const CARDS = [
  { label: 'Accuracy', value: pct(r.correct, PLAN.cases), note: `Wilson 95% ${(lo * 100).toFixed(1)}–${(hi * 100).toFixed(1)}%` },
  { label: 'p95 latency', value: `${(r.p95Ms / 1000).toFixed(2)} s`, note: `p50 ${r.p50Ms} ms` },
  { label: 'Cost / 1k cases', value: formatAmount(cost), badge: cost.provenance, note: 'catalog rate × tokens' },
  { label: 'Unresolved spend', value: '—', note: `${unresolved} entry · blocks live runs` },
]

export const ResultsWindow: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const seen = useInView(ref, { once: true, margin: '0px 0px -15% 0px' })
  const reduced = useReducedMotion()
  const on = seen || reduced

  return (
    <div ref={ref} className={`rp-g-results${on ? ' is-on' : ''}`}>
      <div className="rp-g-win">
        <div className="rp-g-win-bar">
          <span className="rp-g-dots" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
          <span className="rp-g-win-title">
            Results · {PLAN.name} {PLAN.version} · {A}
          </span>
          <SampleChip />
        </div>
        <div className="rp-g-cards">
          {CARDS.map((c, i) => (
            <div key={c.label} className="rp-g-score" style={{ '--i': i } as React.CSSProperties}>
              <span className="rp-g-score-label">{c.label}</span>
              <span className="rp-g-score-value">
                {c.badge && <i className="rp-g-badge">{c.badge}</i>}
                <b className={c.value === '—' ? 'is-null' : undefined}>{c.value}</b>
              </span>
              <span className="rp-g-score-note">{c.note}</span>
            </div>
          ))}
        </div>
        <div className="rp-g-lower">
          <figure className="rp-g-matrix" aria-label={`Confusion matrix, ${PLAN.cases} ${PLAN.split} cases`}>
            <figcaption>Confusion matrix · actual × predicted</figcaption>
            <table>
              <thead>
                <tr>
                  <th aria-hidden="true" />
                  {CLASSES.map((c) => (
                    <th key={c} scope="col" title={c}>
                      {c.slice(0, 4)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {CONFUSION.map((row, i) => (
                  <tr key={CLASSES[i]}>
                    <th scope="row">{CLASSES[i]}</th>
                    {row.map((v, j) => (
                      <td
                        key={j}
                        className={i === j ? 'is-diag' : undefined}
                        style={{ '--a': (v / maxCell).toFixed(3), '--i': i * 5 + j } as React.CSSProperties}
                      >
                        {v}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </figure>
          <div className="rp-g-bars">
            <p className="rp-g-bars-title">Per-class recall</p>
            {CLASSES.map((c, i) => (
              <div key={c} className="rp-g-bar-row" style={{ '--i': i } as React.CSSProperties}>
                <span>{c}</span>
                <span className="rp-g-bar">
                  <i style={{ '--w': (recall[i] / 100).toFixed(3) } as React.CSSProperties} />
                </span>
                <b>{recall[i].toFixed(1)}%</b>
              </div>
            ))}
            <p className="rp-g-kappa">
              Agreement κ {AGREEMENT.kappa.toFixed(2)} with {AGREEMENT.b} · reported as agreement, not accuracy
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
