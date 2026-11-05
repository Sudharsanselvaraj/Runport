import React, { useRef, useState } from 'react'
import { useInView, useReducedMotion } from 'framer-motion'
import { AGREEMENT, CLASSES, CLASS_LABELS, CONFUSION, PLAN, RESULTS, costPer1kCell, formatAmount, pct, perClassRecall, wilson } from '../../../data/sampleRun'

// Card 4: three stat tiles, then one visual chosen with a segmented control:
// per-class recall bars (default; they grow from 0 when the card enters) or the
// confusion matrix. Class labels come from one mapping (CLASS_LABELS), so rows
// and columns never truncate. Reduced motion: bars drawn at full length.

const A = AGREEMENT.a
const r = RESULTS[A]
const [lo, hi] = wilson(r.correct, PLAN.cases)
const cost = costPer1kCell(A)
const recall = perClassRecall()
const maxCell = Math.max(...CONFUSION.flat())
const VIEWS = ['Per class', 'Confusion matrix'] as const
type View = (typeof VIEWS)[number]

export const ResultsPanel: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const seen = useInView(ref, { once: true, margin: '0px 0px -10% 0px' })
  const reduced = useReducedMotion()
  const [view, setView] = useState<View>('Per class')

  const onKey = (e: React.KeyboardEvent) => {
    if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return
    e.preventDefault()
    const next = view === VIEWS[0] ? VIEWS[1] : VIEWS[0]
    const target = e.key === 'Home' ? VIEWS[0] : e.key === 'End' ? VIEWS[1] : next
    setView(target)
    document.getElementById(`rp-g-view-${VIEWS.indexOf(target)}`)?.focus()
  }

  return (
    <div ref={ref} className={`rp-g-results${seen || reduced ? ' is-on' : ''}`}>
      <div className="rp-g-stats">
        <div className="rp-g-stat">
          <span className="rp-g-mono-label">Accuracy</span>
          <b>{pct(r.correct, PLAN.cases)}</b>
          <span className="rp-g-stat-note">
            Wilson 95% {(lo * 100).toFixed(1)}–{(hi * 100).toFixed(1)}%
          </span>
        </div>
        <div className="rp-g-stat">
          <span className="rp-g-mono-label">p95 latency</span>
          <b>{(r.p95Ms / 1000).toFixed(2)} s</b>
          <span className="rp-g-stat-note">p50 {r.p50Ms} ms</span>
        </div>
        <div className="rp-g-stat">
          <span className="rp-g-mono-label">Cost / 1k</span>
          <b>{formatAmount(cost)}</b>
          <span className="rp-g-stat-note">
            <em className="rp-g-pill is-neutral">{cost.provenance}</em>
          </span>
        </div>
      </div>

      <div className="rp-g-seg" role="tablist" aria-label="Results view" onKeyDown={onKey}>
        {VIEWS.map((v, i) => (
          <button
            key={v}
            id={`rp-g-view-${i}`}
            type="button"
            role="tab"
            aria-selected={view === v}
            aria-controls="rp-g-view-panel"
            tabIndex={view === v ? 0 : -1}
            className={view === v ? 'is-active' : undefined}
            onClick={() => setView(v)}
          >
            {v}
          </button>
        ))}
      </div>

      <div id="rp-g-view-panel" role="tabpanel" aria-labelledby={`rp-g-view-${VIEWS.indexOf(view)}`} className="rp-g-view">
        {view === 'Per class' ? (
          <div className="rp-g-bars">
            {CLASSES.map((c, i) => (
              <div key={c} className="rp-g-bar-row" style={{ '--i': i } as React.CSSProperties}>
                <span className="rp-g-bar-name">{CLASS_LABELS[c]}</span>
                <span className="rp-g-bar" aria-hidden="true">
                  <i style={{ '--w': (recall[i] / 100).toFixed(3) } as React.CSSProperties} />
                </span>
                <span className="rp-g-bar-val">{recall[i].toFixed(1)}%</span>
              </div>
            ))}
          </div>
        ) : (
          <table className="rp-g-matrix">
            <caption className="rp-sr-only">
              Confusion matrix for {PLAN.cases} {PLAN.split} cases, actual by predicted
            </caption>
            <thead>
              <tr>
                <th scope="col">
                  <span className="rp-sr-only">actual</span>
                </th>
                {CLASSES.map((c) => (
                  <th key={c} scope="col">
                    {CLASS_LABELS[c]}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {CONFUSION.map((row, i) => (
                <tr key={CLASSES[i]}>
                  <th scope="row">{CLASS_LABELS[CLASSES[i]]}</th>
                  {row.map((v, j) => (
                    <td key={j} className={i === j ? 'is-diag' : undefined} style={{ '--a': (v / maxCell).toFixed(3) } as React.CSSProperties}>
                      {v}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <p className="rp-g-note">Agreement is reported as agreement, not accuracy.</p>
    </div>
  )
}
