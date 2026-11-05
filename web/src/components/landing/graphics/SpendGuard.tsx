import React, { useRef } from 'react'
import { BUDGET_DEFAULTS, formatUsd } from '../../../data/sampleRun'
import { SampleChip } from '../SampleChip'
import { useLoopClock, useLoopWhenVisible } from '../motionKit'
import { budgetFrame, budgetPlan } from './frames'

// Card 3 (tall): a cool-gray beam falls onto a metallic Runport emblem with
// circuit lines running left and right. Below it, a ring fills as sample
// requests are booked against the per-run ceiling; the request that would cross
// the cap is blocked before it is sent, the ring turns to a hard stop, holds,
// then resets. Unpriced requests show an em dash and add nothing. Reduced
// motion: the final blocked state.

const R = 46
const C = 2 * Math.PI * R

export const SpendGuard: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const { active, reduced } = useLoopWhenVisible(ref)
  const t = useLoopClock(active, 0.2)
  const f = budgetFrame(t, reduced)
  const fill = Math.min(1, f.spentUsd / f.capUsd)
  const total = budgetPlan().rows.length

  return (
    <div ref={ref} className={`rp-g-spend${active ? ' is-live' : ''}${f.blocked ? ' is-blocked' : ''}`}>
      <SampleChip className="rp-g-sample" />
      <div className="rp-g-beam" aria-hidden="true" />
      <div className="rp-g-emblem-wrap" aria-hidden="true">
        <svg className="rp-g-circuit" viewBox="0 0 400 120" preserveAspectRatio="none">
          <path d="M0 70 H120 L140 54 H170" />
          <path d="M400 70 H280 L260 54 H230" />
          <path d="M0 92 H90 L112 72 H160" className="is-faint" />
          <path d="M400 92 H310 L288 72 H240" className="is-faint" />
        </svg>
        <span className="rp-g-emblem" />
      </div>

      <div className="rp-g-ring" role="img" aria-label={`Per-run ceiling ${formatUsd(f.capUsd, 2)}. Booked ${formatUsd(f.spentUsd)}.${f.blocked ? ' The next request was blocked before it was sent.' : ''}`}>
        <svg viewBox="0 0 120 120" aria-hidden="true">
          <circle cx="60" cy="60" r={R} className="rp-g-ring-track" />
          <circle cx="60" cy="60" r={R} className="rp-g-ring-fill" strokeDasharray={C} strokeDashoffset={C * (1 - fill)} transform="rotate(-90 60 60)" />
        </svg>
        <div className="rp-g-ring-label" aria-hidden="true">
          <strong>{formatUsd(f.spentUsd, 2)}</strong>
          <span>of {formatUsd(BUDGET_DEFAULTS.perRunUsd, 2)} per run</span>
        </div>
      </div>

      <ol className="rp-g-requests" aria-label="Sample requests checked against the cap">
        {Array.from({ length: total }, (_, i) => {
          const r = f.rows[i]
          return (
            <li key={i} className={r ? (r.blocked ? 'is-blocked' : r.counted ? 'is-booked' : 'is-dash') : 'is-pending'}>
              <span className="rp-g-req-id">{r ? r.id : '·'}</span>
              <span className="rp-g-req-amt">{r ? r.label : ''}</span>
              <span className="rp-g-req-state">{r ? (r.blocked ? 'blocked before sent' : r.counted ? 'booked' : 'unpriced') : ''}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
