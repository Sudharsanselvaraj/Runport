import React from 'react'
import { ArrowRight, Check } from 'lucide-react'
import { LANDING_CONTENT, type RunTarget } from '../../data/landingContent'
import { Reveal } from './motion'
import { BadgeArt, CloudArt, CubeArt, LaptopArt } from './RunIllustrations'

// Where Runport runs: three bordered columns (local, Docker, CI), each with a
// small dark illustration, then a contrasting card that says there is no cloud.

const ART: Record<RunTarget['key'], React.FC> = { local: LaptopArt, docker: CubeArt, ci: BadgeArt }

const newTab = (href: string) => (/^https?:/.test(href) ? { target: '_blank', rel: 'noopener noreferrer' } : {})

export const RunAnywhere: React.FC = () => {
  const c = LANDING_CONTENT.runAnywhere
  return (
    <section className="rp-section rp-ra" id="deploy" aria-labelledby="rp-ra-title">
      <div className="rp-ra-inner">
        <Reveal>
          <p className="rp-eyebrow rp-eyebrow-left">Deploy</p>
          <h2 id="rp-ra-title" className="rp-ra-heading">
            {c.titleLead} <strong>{c.titleKey}</strong> {c.titleTail}
          </h2>
        </Reveal>
        <div className="rp-ra-layout">
          <Reveal delay={0.06} className="rp-ra-group">
            <div className="rp-ra-group-head">
              <img src="/assets/landing/runport-emblem.png" alt="" />
              <span className="rp-ra-product">Runport</span>
              <span className="rp-ra-meta">{c.product}</span>
            </div>
            <div className="rp-ra-cols">
              {c.targets.map((t) => {
                const Art = ART[t.key]
                return (
                <div key={t.key} className="rp-ra-col">
                  <div className="rp-ra-art-wrap">
                    <Art />
                  </div>
                  <h3>{t.title}</h3>
                  <p>{t.body}</p>
                  <a href={t.link.href} {...newTab(t.link.href)}>
                    {t.link.label} <ArrowRight size={14} aria-hidden="true" />
                  </a>
                </div>
                )
              })}
            </div>
          </Reveal>

          <span className="rp-ra-arrow" aria-hidden="true">
            <ArrowRight size={20} strokeWidth={1.4} />
          </span>

          <Reveal delay={0.16} className="rp-ra-callout">
            <div className="rp-ra-callout-head">
              <img src="/assets/landing/runport-emblem.png" alt="" />
              <span>Local only</span>
            </div>
            <div className="rp-ra-badge">
              <CloudArt />
            </div>
            <h3>{c.callout.title}</h3>
            <p>{c.callout.body}</p>
            <ul>
              {c.callout.checks.map((k) => (
                <li key={k}>
                  <Check size={14} strokeWidth={2} aria-hidden="true" />
                  {k}
                </li>
              ))}
            </ul>
            <a className="rp-ra-cta" href={c.callout.href} target="_blank" rel="noopener noreferrer">
              {c.callout.cta}
            </a>
          </Reveal>
        </div>
      </div>
    </section>
  )
}
