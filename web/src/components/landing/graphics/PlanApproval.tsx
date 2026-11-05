import React, { useRef } from 'react'
import { Check, Fingerprint, X } from 'lucide-react'
import { PLAN } from '../../../data/sampleRun'
import { SampleChip } from '../SampleChip'
import { PointerParallax, useLoopClock, useLoopWhenVisible } from '../motionKit'
import { planFrame } from './frames'

// Card 2: three slightly rotated glass panels (plan, approval, stale) that
// float and follow the pointer. Every 3 seconds the demo either changes the
// plan (new fingerprint, so the old approval is rejected) or records a new
// approval for it. frames.planFrame guarantees "approved" only ever appears when
// the approval matches the current fingerprint. Reduced motion shows the
// rejected state, which carries both fingerprints.

const sha = (fp: string) => `sha256:${fp}…`

export const PlanApproval: React.FC = () => {
  const ref = useRef<HTMLDivElement>(null)
  const { active, reduced } = useLoopWhenVisible(ref)
  const t = useLoopClock(active, 0.25)
  const f = planFrame(t, reduced)
  const ok = f.status === 'approved'

  return (
    <div ref={ref} className={`rp-g-plan${active ? ' is-live' : ''}`}>
      <SampleChip className="rp-g-sample" />
      <PointerParallax className="rp-g-plan-stack">
        <div className="rp-g-panel is-stale" style={{ '--d': 0.4, '--r': '-7deg' } as React.CSSProperties}>
          <span className="rp-g-panel-kicker">Superseded plan</span>
          <code>{sha(f.stale)}</code>
        </div>
        <div className="rp-g-panel is-plan" style={{ '--d': 0.8, '--r': '4deg' } as React.CSSProperties}>
          <span className="rp-g-panel-kicker">
            <Fingerprint size={12} aria-hidden="true" /> Plan · {PLAN.name} {PLAN.version}
          </span>
          <code key={f.fingerprint} className="rp-g-fp">
            {sha(f.fingerprint)}
          </code>
          <span className="rp-g-panel-meta">models · routes · dataset · template · caps</span>
        </div>
        <div className={`rp-g-panel is-approval ${ok ? 'is-ok' : 'is-bad'}`} style={{ '--d': 1.3, '--r': '-2deg' } as React.CSSProperties}>
          <div key={`${f.status}-${f.approvedFor}-${f.fingerprint}`} className="rp-g-flip">
            <span className="rp-g-panel-kicker">
              {ok ? <Check size={12} aria-hidden="true" /> : <X size={12} aria-hidden="true" />}
              {ok ? 'Approved' : 'Rejected'}
            </span>
            <span className="rp-g-panel-body">{ok ? `Typed approval for ${sha(f.approvedFor)}` : `Approval was for ${sha(f.approvedFor)}; the plan is now ${sha(f.fingerprint)}`}</span>
          </div>
        </div>
      </PointerParallax>
      <p className="rp-sr-only" aria-live="off">
        Approval is bound to the plan fingerprint. When the plan changes, the earlier approval is rejected until a new one is given.
      </p>
    </div>
  )
}
