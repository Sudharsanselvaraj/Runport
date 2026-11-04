import React from 'react'
import { LANDING_CONTENT } from '../../data/landingContent'
import { CountUp, Reveal } from './motion'

// Reference: four mono 48px stats on a 700px column over a horizon glow, then a
// 700 × 330 split card. Runport shows verifiable product facts, not customer
// metrics, and quotes a design invariant rather than an invented testimonial.
export const MetricsSection: React.FC = () => {
  const c = LANDING_CONTENT.metrics
  return (
    <section className="rp-section rp-metrics" aria-label="Runport by the numbers">
      <div className="rp-glow" aria-hidden="true">
        <img src="/assets/landing/hero-bg.png" alt="" />
      </div>
      <div className="rp-narrow">
        <div className="rp-stats">
          {c.stats.map((s, i) => (
            <Reveal key={s.label} className="rp-stat" delay={0.06 * i}>
              <CountUp className="rp-stat-value" value={s.value} decimals={s.decimals} prefix={s.prefix} suffix={s.suffix} />
              <span className="rp-stat-label">{s.label}</span>
            </Reveal>
          ))}
        </div>

        <Reveal className="rp-proof rp-glass-card" delay={0.1}>
          <div className="rp-proof-copy">
            <div>
              <h3 className="rp-h3">{c.proof.quote}</h3>
              <p className="rp-body">{c.proof.body}</p>
            </div>
            <div>
              <p className="rp-title">{c.proof.source}</p>
              <p className="rp-body" style={{ marginTop: -9 }}>{c.proof.sourceDetail}</p>
            </div>
          </div>
          <div className="rp-proof-media">
            <img src="/assets/landing/testimonial-bg.jpg" alt="" loading="lazy" />
            <div className="rp-proof-facts">
              {c.proof.facts.map((f) => (
                <div key={f.label}>
                  <b>{f.value}</b>
                  <span className="rp-body">{f.label}</span>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  )
}
