import React, { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Menu, X } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'
import { EASE_OUT } from './motion'

const newTab = (href: string) => (/^https?:/.test(href) ? { target: '_blank', rel: 'noopener noreferrer' } : {})

export const Navigation: React.FC = () => {
  const [open, setOpen] = useState(false)
  const c = LANDING_CONTENT.navigation

  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false)
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const linkProps = (external?: boolean) => (external ? { target: '_blank', rel: 'noopener noreferrer' } : {})

  return (
    <>
      <header className="rp-nav">
        <nav className="rp-nav-row" aria-label="Primary">
          <a href="#top" className="rp-brand" onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}>
            <img src="/assets/landing/runport-emblem.png" alt="" />
            <span>{c.brandName}</span>
          </a>
          <div className="rp-nav-links">
            {c.links.map((l) => (
              <a key={l.label} href={l.href} {...linkProps(l.isExternal)}>
                {l.label}
              </a>
            ))}
          </div>
          <div className="rp-nav-actions">
            <a href={LANDING_CONTENT.repo} target="_blank" rel="noopener noreferrer" className="rp-pill rp-pill-sm rp-pill-glass">
              {c.ctaSecondary}
            </a>
            <a href={c.ctaPrimaryHref} {...newTab(c.ctaPrimaryHref)} className="rp-pill rp-pill-sm rp-pill-dark">
              {c.ctaPrimary}
            </a>
            <button
              type="button"
              className="rp-pill rp-pill-glass rp-nav-toggle"
              aria-label={open ? 'Close menu' : 'Open menu'}
              aria-expanded={open}
              onClick={() => setOpen((v) => !v)}
            >
              {open ? <X size={16} /> : <Menu size={16} />}
            </button>
          </div>
        </nav>
      </header>
      <AnimatePresence>
        {open && (
          <motion.div
            className="rp-nav-sheet"
            initial={{ opacity: 0, y: -8, filter: 'blur(6px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            exit={{ opacity: 0, y: -8, filter: 'blur(6px)' }}
            transition={{ duration: 0.3, ease: EASE_OUT }}
          >
            {c.links.map((l) => (
              <a key={l.label} href={l.href} onClick={() => setOpen(false)} {...linkProps(l.isExternal)}>
                {l.label}
              </a>
            ))}
            <a href={LANDING_CONTENT.repo} target="_blank" rel="noopener noreferrer" onClick={() => setOpen(false)}>
              {c.ctaSecondary}
            </a>
            <a href={c.ctaPrimaryHref} {...newTab(c.ctaPrimaryHref)} className="rp-pill rp-pill-dark" onClick={() => setOpen(false)}>
              {c.ctaPrimary}
            </a>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  )
}
