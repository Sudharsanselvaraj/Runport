import React from 'react'
import { Github } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'
import { FEATURE_ICONS } from './PricingSection'
import { Reveal } from './motion'

export const Footer: React.FC = () => {
  const c = LANDING_CONTENT.footer
  const external = (href: string) => (href.startsWith('http') ? { target: '_blank', rel: 'noopener noreferrer' } : {})
  return (
    <footer className="rp-footer">
      <Reveal className="rp-footer-row" y={20}>
        <div className="rp-footer-brand">
          <span className="rp-brand">
            <img src="/assets/landing/runport-emblem.png" alt="" />
            {c.brandName}
          </span>
          <p className="rp-body">{c.tagline}</p>
          <div className="rp-socials">
            <a href={LANDING_CONTENT.repo} target="_blank" rel="noopener noreferrer" aria-label="Runport on GitHub">
              <Github size={16} />
            </a>
          </div>
        </div>
        <div className="rp-footer-cols">
          {c.columns.map((col) => {
            const Icon = FEATURE_ICONS[col.icon]
            return (
              <div key={col.title} className="rp-footer-col">
                <h3><Icon size={14} />{col.title}</h3>
                {col.links.map((l) => (
                  <a key={l.label} href={l.href} {...external(l.href)}>
                    {l.label}
                  </a>
                ))}
              </div>
            )
          })}
        </div>
      </Reveal>
      <div className="rp-footer-base">
        <p className="rp-body" style={{ color: 'var(--rp-white)' }}>{c.closing}</p>
        <small>{c.copyright}</small>
      </div>
    </footer>
  )
}
