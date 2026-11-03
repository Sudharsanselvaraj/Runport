import React from 'react'
import { motion } from 'framer-motion'
import { LANDING_CONTENT } from '../../data/landingContent'

export const MetricsSection: React.FC = () => {
  const content = LANDING_CONTENT.metricsSection

  return (
    <section className="rp-metrics-section">
      <div className="rp-container">
        {/* 4 Stat Numbers Row */}
        <div className="rp-stats-row">
          {content.stats.map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: i * 0.1 }}
            >
              <div className="rp-stat-value">{stat.value}</div>
              <div className="rp-stat-label">{stat.label}</div>
            </motion.div>
          ))}
        </div>

        {/* Testimonial & Impact Bento */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
          className="rp-testimonial-bento"
        >
          {/* Left Text Half */}
          <div className="rp-testimonial-left">
            <div>
              <p
                style={{
                  fontFamily: 'var(--rp-font-display)',
                  fontSize: 'clamp(20px, 2.2vw, 26px)',
                  fontWeight: 500,
                  lineHeight: 1.35,
                  color: '#ffffff',
                  marginBottom: '20px',
                }}
              >
                {content.testimonial.quote}
              </p>
              <p className="rp-body-muted" style={{ lineHeight: 1.6, maxWidth: '480px' }}>
                {content.testimonial.body}
              </p>
            </div>

            <div style={{ marginTop: '40px' }}>
              <div style={{ fontSize: '15px', fontWeight: 600, color: '#ffffff' }}>{content.testimonial.author}</div>
              <div style={{ fontSize: '13px', color: 'rgba(255, 255, 255, 0.45)', marginTop: '2px' }}>
                {content.testimonial.role}
              </div>
            </div>
          </div>

          {/* Right Scenic Card Half */}
          <div className="rp-testimonial-right">
            <div className="rp-testimonial-right-overlay" />

            <div style={{ position: 'relative', zIndex: 2, display: 'flex', justifyContent: 'space-between' }}>
              <div>
                <div style={{ fontSize: 'clamp(28px, 3vw, 36px)', fontWeight: 600, color: '#ffffff' }}>
                  {content.testimonial.impactStats[0].value}
                </div>
                <div style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.7)', marginTop: '2px' }}>
                  {content.testimonial.impactStats[0].label}
                </div>
              </div>

              <div>
                <div style={{ fontSize: 'clamp(28px, 3vw, 36px)', fontWeight: 600, color: '#ffffff' }}>
                  {content.testimonial.impactStats[1].value}
                </div>
                <div style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.7)', marginTop: '2px' }}>
                  {content.testimonial.impactStats[1].label}
                </div>
              </div>
            </div>

            <div style={{ position: 'relative', zIndex: 2, marginTop: 'auto', paddingTop: '40px' }}>
              <div style={{ fontSize: 'clamp(28px, 3vw, 36px)', fontWeight: 600, color: '#ffffff' }}>
                {content.testimonial.impactStats[2].value}
              </div>
              <div style={{ fontSize: '12px', color: 'rgba(255, 255, 255, 0.7)', marginTop: '2px' }}>
                {content.testimonial.impactStats[2].label}
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  )
}
