import React from 'react'
import { LANDING_CONTENT } from '../../data/landingContent'
import { Reveal } from './motion'

export const FinalCTA: React.FC = () => {
  const c = LANDING_CONTENT.finalCta
  return (
    <section className="rp-final">
      <Reveal className="rp-mark" y={30}>
        <img src="/assets/landing/runport-emblem.png" alt="" />
      </Reveal>
      <Reveal className="rp-final-copy" delay={0.08}>
        <div>
          <h2 className="rp-h2 rp-fade-heading">
            {c.titleA} {c.titleB}
          </h2>
          <p className="rp-body">{c.subheading}</p>
        </div>
        <a href={c.ctaHref} target="_blank" rel="noopener noreferrer" className="rp-pill rp-pill-glass">
          {c.cta}
        </a>
      </Reveal>
    </section>
  )
}
