import React from 'react'
import { motion } from 'framer-motion'
import { ArrowRight, Play, Terminal, Shield } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'

interface HeroSectionProps {
  onLaunchWorkbench: () => void
}

export const HeroSection: React.FC<HeroSectionProps> = ({ onLaunchWorkbench }) => {
  const content = LANDING_CONTENT.hero

  return (
    <section className="rp-hero-section">
      {/* Cinematic Dreamscape Background */}
      <div className="rp-hero-bg" />
      <div className="rp-hero-fade" />

      {/* Main Content */}
      <div className="rp-container rp-hero-content">
        {/* Top Badge */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
          className="rp-hero-badge"
        >
          <Shield size={13} style={{ color: '#10b981' }} />
          <span>{content.badge}</span>
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
          className="rp-h1"
        >
          {content.title}
          <br />
          <span style={{ color: 'rgba(255, 255, 255, 0.9)' }}>{content.titleAccent}</span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
          className="rp-body-lead"
          style={{ maxWidth: '580px', margin: '22px auto 0 auto' }}
        >
          {content.description}
        </motion.p>

        {/* Dual Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.3, ease: [0.16, 1, 0.3, 1] }}
          className="rp-hero-actions"
        >
          <button onClick={onLaunchWorkbench} className="rp-btn-pill rp-btn-glass">
            <Terminal size={15} />
            <span>{content.ctaPrimary}</span>
          </button>
          <a href="#features" className="rp-btn-pill rp-btn-dark">
            <Play size={14} style={{ fill: 'currentColor' }} />
            <span>{content.ctaSecondary}</span>
          </a>
        </motion.div>
      </div>

      {/* Trusted By Ecosystem Marquee */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ duration: 1, delay: 0.5 }}
        className="rp-trusted-section"
      >
        <p className="rp-trusted-label">{content.trustedLabel}</p>
        <div className="rp-trusted-row">
          {content.trustedLogos.map((logo) => (
            <span key={logo} className="rp-trusted-item">
              {logo}
            </span>
          ))}
        </div>
      </motion.div>
    </section>
  )
}
