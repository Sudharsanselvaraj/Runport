import React from 'react'
import { motion } from 'framer-motion'
import { LANDING_CONTENT } from '../../data/landingContent'

export const StatementBanner: React.FC = () => {
  const content = LANDING_CONTENT.statement

  return (
    <section className="rp-statement-section">
      <div className="rp-container-narrow">
        <motion.div
          initial={{ opacity: 0, y: 32 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
        >
          <h2 className="rp-statement-text">
            LLM benchmarking shouldn't feel this <span style={{ color: 'rgba(255, 255, 255, 0.55)' }}>scattered.</span>
          </h2>
          <p
            className="rp-body-lead"
            style={{
              maxWidth: '620px',
              margin: '30px auto 0 auto',
              textAlign: 'center',
              color: 'var(--rp-text-muted)',
            }}
          >
            {content.subtext}
          </p>
        </motion.div>
      </div>
    </section>
  )
}
