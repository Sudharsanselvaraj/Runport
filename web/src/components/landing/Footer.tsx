import React from 'react'
import { Github, Twitter, MessageCircle } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'

interface FooterProps {
  onLaunchWorkbench: () => void
}

export const Footer: React.FC<FooterProps> = ({ onLaunchWorkbench }) => {
  const content = LANDING_CONTENT.footer

  return (
    <footer className="rp-footer-section">
      <div className="rp-container">
        <div className="rp-footer-grid">
          {/* Brand Info */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
              <img src="/assets/landing/runport-emblem.png" alt="Runport" width="22" height="22" />
              <span style={{ fontSize: '15px', fontWeight: 600, letterSpacing: '0.04em', color: '#ffffff' }}>
                {content.brandName}
              </span>
            </div>
            <p className="rp-body-muted" style={{ maxWidth: '300px', lineHeight: 1.6, marginBottom: '24px' }}>
              {content.tagline}
            </p>

            {/* Social Icons */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
              <a
                href="https://github.com/Sudharsanselvaraj/runport"
                target="_blank"
                rel="noopener noreferrer"
                style={{ color: 'rgba(255, 255, 255, 0.5)', transition: 'color 0.2s' }}
                aria-label="GitHub"
              >
                <Github size={18} />
              </a>
              <a
                href="#"
                style={{ color: 'rgba(255, 255, 255, 0.5)', transition: 'color 0.2s' }}
                aria-label="Discord"
              >
                <MessageCircle size={18} />
              </a>
              <a
                href="#"
                style={{ color: 'rgba(255, 255, 255, 0.5)', transition: 'color 0.2s' }}
                aria-label="Twitter / X"
              >
                <Twitter size={18} />
              </a>
            </div>
          </div>

          {/* Links Columns */}
          <div className="rp-footer-cols">
            {content.columns.map((col) => (
              <div key={col.title}>
                <div className="rp-footer-col-title">{col.title}</div>
                {col.links.map((link) => (
                  <a
                    key={link.label}
                    href={link.href}
                    onClick={(e) => {
                      if (link.label === 'Workbench' || link.label === 'Terminal TUI') {
                        e.preventDefault()
                        onLaunchWorkbench()
                      }
                    }}
                    className="rp-footer-link"
                  >
                    {link.label}
                  </a>
                ))}
              </div>
            ))}
          </div>
        </div>

        {/* Bottom bar */}
        <div className="rp-footer-bottom">
          <div>{content.copyright}</div>
          <div style={{ display: 'flex', gap: '20px' }}>
            <span style={{ opacity: 0.6 }}>v0.1.0-alpha</span>
            <span style={{ opacity: 0.6 }}>Local-First Architecture</span>
          </div>
        </div>
      </div>
    </footer>
  )
}
