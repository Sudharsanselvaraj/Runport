import React, { useRef } from 'react'
import { formatUsd } from '../../../data/sampleRun'
import { useLoopClock, useLoopWhenVisible } from '../motionKit'
import { spendFrame } from './frames'

// Card 3: a small emblem under a very faint beam, a 150 px ring and exactly
// three request rows. The ring fills over 8 s (ease-in-out) to the per-run cap,
// the third request shows "blocked before sent", the frame holds 1.5 s, then the
// loop resets. An unpriced request would show an em dash. Reduced motion: the
// final, blocked frame.

const R = 66
const C = 2 * Math.PI * R
const STATE = { queued: 'queued', booked: 'booked', unpriced: 'unpriced', blocked: 'blocked before sent' } as const

export const SpendGuard: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const { active, reduced } = useLoopWhenVisible(ref)
  const t = useLoopClock(active, 0.1)
  const f = spendFrame(t, reduced)
  const fill = Math.min(1, f.valueUsd / f.capUsd)

  return (
    <div ref={ref} className={`rp-g-spend${f.blocked ? ' is-blocked' : ''}`}>
      <div className="rp-g-spend-top" aria-hidden="true">
        <span className="rp-g-beam" />
        <span className="rp-g-emblem" />
      </div>
      <div
        className="rp-g-ring"
        role="img"
        aria-label={`${formatUsd(f.valueUsd, 2)} of the ${formatUsd(f.capUsd, 2)} per-run ceiling booked.${f.blocked ? ' The next request was blocked before it was sent.' : ''}`}
      >
        <svg viewBox="0 0 150 150" aria-hidden="true">
          <circle cx="75" cy="75" r={R} className="rp-g-ring-track" />
          <circle cx="75" cy="75" r={R} className="rp-g-ring-fill" strokeDasharray={C} strokeDashoffset={C * (1 - fill)} transform="rotate(-90 75 75)" />
        </svg>
        <div className="rp-g-ring-label" aria-hidden="true">
          <strong>{formatUsd(f.valueUsd, 2)}</strong>
          <span>of {formatUsd(f.capUsd, 2)} per run</span>
        </div>
      </div>
      <ol className="rp-g-requests" aria-label="Requests checked against the ceiling">
        {f.rows.map((r) => (
          <li key={r.id} className={`is-${r.state}`}>
            <i className="rp-g-dot" aria-hidden="true" />
            <span className="rp-g-req-id">{r.id}</span>
            <span className="rp-g-req-amt">{r.label}</span>
            <span className="rp-g-req-state">{STATE[r.state]}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}
