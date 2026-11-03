import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Menu, X, Terminal, ArrowRight } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'

interface NavigationProps {
  onLaunchWorkbench: () => void
}

export const Navigation: React.FC<NavigationProps> = ({ onLaunchWorkbench }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const content = LANDING_CONTENT.navigation

  return (
    <header className="rp-nav-outer">
      <nav className="rp-nav-inner">
        {/* Brand */}
        <a href="#" className="rp-nav-brand">
          <img src="/assets/landing/runport-emblem.png" alt="Runport" width="22" height="22" style={{ objectFit: 'contain' }} />
          <span>{content.brandName}</span>
        </a>

        {/* Center Links (Desktop) */}
        <div className="rp-nav-links">
          {content.links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              target={link.isExternal ? '_blank' : undefined}
              rel={link.isExternal ? 'noopener noreferrer' : undefined}
              className="rp-nav-link"
            >
              {link.label}
            </a>
          ))}
        </div>

        {/* Right Actions */}
        <div className="rp-nav-actions">
          <a
            href="https://github.com/Sudharsanselvaraj/runport"
            target="_blank"
            rel="noopener noreferrer"
            className="rp-btn-pill rp-btn-glass rp-nav-desktop-action"
            style={{ height: '36px', padding: '0 16px', fontSize: '13px' }}
          >
            {content.ctaSecondary}
          </a>
          <button
            onClick={onLaunchWorkbench}
            className="rp-btn-pill rp-btn-solid-white rp-nav-desktop-action"
            style={{ height: '36px', padding: '0 16px', fontSize: '13px' }}
          >
            <span>{content.ctaPrimary}</span>
            <ArrowRight size={13} />
          </button>

          {/* Mobile Menu Button */}
          <button
            className="rp-btn-pill rp-btn-glass rp-nav-mobile-toggle"
            style={{ height: '36px', width: '36px', padding: 0 }}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Toggle Navigation Menu"
          >
            {mobileMenuOpen ? <X size={16} /> : <Menu size={16} />}
          </button>
        </div>
      </nav>

      {/* Mobile Drawer */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.2 }}
            style={{
              position: 'fixed',
              top: '80px',
              left: '20px',
              right: '20px',
              background: '#0d0d12',
              border: '1px solid rgba(255, 255, 255, 0.12)',
              borderRadius: '20px',
              padding: '24px',
              display: 'flex',
              flexDirection: 'column',
              gap: '16px',
              pointerEvents: 'auto',
              boxShadow: '0 20px 40px rgba(0,0,0,0.8)',
              zIndex: 999,
            }}
          >
            {content.links.map((link) => (
              <a
                key={link.label}
                href={link.href}
                onClick={() => setMobileMenuOpen(false)}
                style={{ color: '#ffffff', textDecoration: 'none', fontSize: '16px', fontWeight: 500 }}
              >
                {link.label}
              </a>
            ))}
            <hr style={{ borderColor: 'rgba(255,255,255,0.08)', margin: '8px 0' }} />
            <button
              onClick={() => {
                setMobileMenuOpen(false)
                onLaunchWorkbench()
              }}
              className="rp-btn-pill rp-btn-solid-white"
              style={{ width: '100%', height: '42px' }}
            >
              <Terminal size={14} />
              <span>{content.ctaPrimary}</span>
            </button>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  )
}
