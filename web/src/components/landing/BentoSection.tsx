import React from 'react'
import { Pause, Play } from 'lucide-react'
import { useReducedMotion } from 'framer-motion'
import { LANDING_CONTENT } from '../../data/landingContent'
import { BentoCard, MotionPauseProvider, Reveal, useMotionPause } from './motionKit'
import { TargetsOrbit } from './graphics/TargetsOrbit'
import { PlanApproval } from './graphics/PlanApproval'
import { SpendGuard } from './graphics/SpendGuard'
import { ResultsPanel } from './graphics/ResultsPanel'
import '../../styles/bento.css'

// "What Runport does": four calm cards on a 12-column grid.
// Desktop: Targets (6) + Plan and approval (6) at 380 px, then Spend guard (4) +
// Results (8) at 420 px. Each card has one slow loop that runs only on screen,
// with the tab visible, and stops with the pause control below the grid.

const PauseToggle: React.FC = () => {
  const { paused, setPaused } = useMotionPause()
  const reduced = useReducedMotion()
  if (reduced) return null
  return (
    <button type="button" className="rp-bento-pause" onClick={() => setPaused(!paused)} aria-pressed={paused}>
      {paused ? <Play size={12} aria-hidden="true" /> : <Pause size={12} aria-hidden="true" />}
      {paused ? 'Play animations' : 'Pause animations'}
    </button>
  )
}

const CardText: React.FC<{ id: string; title: string; body: string }> = ({ id, title, body }) => (
  <header className="rp-bento-text">
    <h3 id={id}>{title}</h3>
    <p>{body}</p>
  </header>
)

export const BentoSection: React.FC = () => {
  const c = LANDING_CONTENT.bento
  return (
    <MotionPauseProvider>
      <section id="features" className="rp-bento" aria-labelledby="rp-bento-title">
        <div className="rp-bento-inner">
          <Reveal className="rp-bento-head">
            <p className="rp-eyebrow">{c.eyebrow}</p>
            <h2 id="rp-bento-title" className="rp-h2 rp-fade-heading">
              {c.titleA}
              <br />
              {c.titleB}
            </h2>
            <p className="rp-body">{c.subheading}</p>
          </Reveal>
          <div className="rp-bento-grid">
            <BentoCard className="is-targets" index={0} labelledBy="rp-b-targets">
              <CardText id="rp-b-targets" {...c.cards.targets} />
              <TargetsOrbit />
            </BentoCard>
            <BentoCard className="is-plan" index={1} labelledBy="rp-b-plan">
              <CardText id="rp-b-plan" {...c.cards.plan} />
              <PlanApproval />
            </BentoCard>
            <BentoCard className="is-spend" index={2} labelledBy="rp-b-spend">
              <CardText id="rp-b-spend" {...c.cards.spend} />
              <SpendGuard />
            </BentoCard>
            <BentoCard className="is-results" index={3} labelledBy="rp-b-results">
              <CardText id="rp-b-results" {...c.cards.results} />
              <ResultsPanel />
            </BentoCard>
          </div>
          <div className="rp-bento-foot">
            <p className="rp-bento-caption">{c.caption}</p>
            <PauseToggle />
          </div>
        </div>
      </section>
    </MotionPauseProvider>
  )
}
