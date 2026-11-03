import React from 'react'
import { motion } from 'framer-motion'
import { Terminal, ArrowRight } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'

interface FinalCTAProps {
  onLaunchWorkbench: () => void
}

export const FinalCTA: React.FC<FinalCTAProps> = ({ onLaunchWorkbench }) => {
  const content = LANDING_CONTENT.finalCta

  return (
    <section className="rp-final-cta-section">
      <div className="rp-container-narrow">
        {/* Emblem */}
        <motion.div
          initial={{ opacity: 0, scale: 0.85 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="rp-emblem-container"
          style={{ width: '90px', height: '90px', margin: '0 auto 28px auto' }}
        >
          <img src="/assets/landing/runport-emblem.png" alt="Runport" className="rp-emblem-img" />
        </motion.div>

        {/* Headline */}
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="rp-h2"
        >
          {content.heading}
        </motion.h2>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.1 }}
          className="rp-body-lead"
          style={{ maxWidth: '520px', margin: '16px auto 36px auto' }}
        >
          {content.subheading}
        </motion.p>

        {/* Actions */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.2 }}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '14px' }}
        >
          <button onClick={onLaunchWorkbench} className="rp-btn-pill rp-btn-solid-white">
            <Terminal size={15} />
            <span>Launch Workbench</span>
          </button>
          <a
            href="https://github.com/Sudharsanselvaraj/runport"
            target="_blank"
            rel="noopener noreferrer"
            className="rp-btn-pill rp-btn-glass"
          >
            <span>Read Docs</span>
            <ArrowRight size={14} />
          </a>
        </motion.div>
      </div>
    </section>
  )
}
