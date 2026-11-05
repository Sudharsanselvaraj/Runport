import React, { useRef } from 'react'
import { PLAN } from '../../../data/sampleRun'
import { useLoopClock, useLoopWhenVisible } from '../motionKit'
import { planFrame } from './frames'

// Card 2: one glass card with the plan name, the first 12 characters of its
// SHA-256 fingerprint and a status pill. 10 s loop: Approved for A; the plan
// changes and the fingerprint morphs to B character by character (600 ms) while
// the pill reads Checking; then Rejected, with a one-line reason; then reset.
// frames.planFrame never pairs Approved with a changed fingerprint (tested).
// Reduced motion: the rejected frame.

const LABEL = { approved: 'Approved', checking: 'Checking', rejected: 'Rejected' } as const

export const PlanApproval: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const { active, reduced } = useLoopWhenVisible(ref)
  const t = useLoopClock(active, 0.05)
  const f = planFrame(t, reduced)

  return (
    <div ref={ref} className="rp-g-plan">
      <div className="rp-g-glass">
        <div className="rp-g-glass-row">
          <span className="rp-g-mono-label">Plan</span>
          <span className={`rp-g-pill is-${f.status}`}>{LABEL[f.status]}</span>
        </div>
        <p className="rp-g-planname">
          {PLAN.name} {PLAN.version}
        </p>
        <code className="rp-g-fp" aria-label={`Fingerprint sha256 ${f.shown}`}>
          <span className="rp-g-fp-pre">sha256:</span>
          {f.shown.split('').map((ch, i) => (
            <span key={i} className={f.changed && ch !== f.approvedFor[i] ? 'is-new' : undefined}>
              {ch}
            </span>
          ))}
        </code>
        <p className={`rp-g-change${f.changed ? ' is-on' : ''}`}>Plan changed</p>
        <p className={`rp-g-reason${f.reason ? ' is-on' : ''}`}>{f.reason ?? ' '}</p>
      </div>
    </div>
  )
}
