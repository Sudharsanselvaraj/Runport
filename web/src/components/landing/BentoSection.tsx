import React from 'react'
import { Pause, Play } from 'lucide-react'
import { useReducedMotion } from 'framer-motion'
import { LANDING_CONTENT } from '../../data/landingContent'
import { CONNECTOR_COUNTS } from '../../data/connectors'
import { BentoCard, MotionPauseProvider, Reveal, useMotionPause } from './motionKit'
import { TargetsOrbit } from './graphics/TargetsOrbit'
import { PlanApproval } from './graphics/PlanApproval'
import { SpendGuard } from './graphics/SpendGuard'
import { ResultsWindow } from './graphics/ResultsWindow'
import '../../styles/bento.css'

// "What Runport does": a bento grid of four cards, each with its own motion
// graphic. Desktop: three columns, with Targets and Plan in row 1, Spend guard
// spanning two rows on the right, and Results spanning two columns in row 2.
// Loops stop off screen, when the tab is hidden, or via the pause control.

const PauseToggle: React.FC = () => {
  const { paused, setPaused } = useMotionPause()
  const reduced = useReducedMotion()
  if (reduced) return null
  return (
    <button type="button" className="rp-bento-pause" onClick={() => setPaused(!paused)} aria-pressed={paused}>
      {paused ? <Play size={13} aria-hidden="true" /> : <Pause size={13} aria-hidden="true" />}
      {paused ? 'Play animations' : 'Pause animations'}
    </button>
  )
}

const CardText: React.FC<{ id: string; title: string; body: string; extra?: string }> = ({ id, title, body, extra }) => (
  <div className="rp-bento-text">
    <h3 id={id}>{title}</h3>
    <p>
      {body}
      {extra && <span className="rp-bento-extra"> {extra}</span>}
    </p>
  </div>
)

export const BentoSection: React.FC = () => {
  const c = LANDING_CONTENT.bento
  return (
    <MotionPauseProvider>
      <section id="features" className="rp-section rp-bento" aria-labelledby="rp-bento-title">
        <div className="rp-bento-inner">
          <Reveal className="rp-bento-head">
            <p className="rp-eyebrow">{c.eyebrow}</p>
            <h2 id="rp-bento-title" className="rp-h2 rp-fade-heading">
              {c.titleA}
              <br />
              {c.titleB}
            </h2>
            <p className="rp-body">{c.subheading}</p>
            <PauseToggle />
          </Reveal>
          <div className="rp-bento-grid">
            <BentoCard className="is-targets" index={0} labelledBy="rp-b-targets">
              <CardText
                id="rp-b-targets"
                {...c.cards.targets}
                extra={`${CONNECTOR_COUNTS.supported} supported and ${CONNECTOR_COUNTS.experimental} experimental connectors today.`}
              />
              <div className="rp-bento-art">
                <TargetsOrbit />
              </div>
            </BentoCard>
            <BentoCard className="is-plan" index={1} labelledBy="rp-b-plan">
              <CardText id="rp-b-plan" {...c.cards.plan} />
              <div className="rp-bento-art">
                <PlanApproval />
              </div>
            </BentoCard>
            <BentoCard className="is-spend" index={2} labelledBy="rp-b-spend">
              <CardText id="rp-b-spend" {...c.cards.spend} />
              <div className="rp-bento-art">
                <SpendGuard />
              </div>
            </BentoCard>
            <BentoCard className="is-results" index={3} labelledBy="rp-b-results">
              <CardText id="rp-b-results" {...c.cards.results} />
              <div className="rp-bento-art">
                <ResultsWindow />
              </div>
            </BentoCard>
          </div>
        </div>
      </section>
    </MotionPauseProvider>
  )
}
