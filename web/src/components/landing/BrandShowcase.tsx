import React from 'react'
import { motion } from 'framer-motion'
import { Shield, Layers, BarChart2 } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'

export const BrandShowcase: React.FC = () => {
  const content = LANDING_CONTENT.platformShowcase

  const renderIcon = (name: string) => {
    switch (name) {
      case 'Folder':
        return <Shield size={18} style={{ color: '#10b981' }} />
      case 'Layers':
        return <Layers size={18} style={{ color: '#3b82f6' }} />
      case 'BarChart2':
      default:
        return <BarChart2 size={18} style={{ color: '#f59e0b' }} />
    }
  }

  return (
    <section className="rp-platform-section">
      <div className="rp-platform-fade-top" />
      <div className="rp-platform-fade-bottom" />

      <div className="rp-container" style={{ position: 'relative', zIndex: 3 }}>
        {/* Title & Subtitle */}
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.8 }}
          style={{ maxWidth: '640px', margin: '0 auto' }}
        >
          <h2 className="rp-h2">{content.heading}</h2>
          <p className="rp-body-lead" style={{ marginTop: '16px' }}>
            {content.description}
          </p>
        </motion.div>

        {/* 3D Metallic Emblem */}
        <motion.div
          initial={{ opacity: 0, scale: 0.85 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
          className="rp-emblem-container"
        >
          <img src="/assets/landing/runport-emblem.png" alt="Runport Hexagonal Emblem" className="rp-emblem-img" />
        </motion.div>

        {/* 3 Pillars Row */}
        <div className="rp-pillars-row">
          {content.pillars.map((pillar, idx) => (
            <motion.div
              key={pillar.title}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: idx * 0.1 }}
              style={{
                padding: '24px',
                borderRadius: '16px',
                background: 'rgba(12, 12, 16, 0.7)',
                border: '1px solid rgba(255, 255, 255, 0.08)',
                backdropFilter: 'blur(12px)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px' }}>
                {renderIcon(pillar.icon)}
                <span style={{ fontSize: '16px', fontWeight: 600, color: '#ffffff' }}>{pillar.title}</span>
              </div>
              <p className="rp-body-muted" style={{ fontSize: '13.5px', lineHeight: 1.55 }}>
                {pillar.description}
              </p>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
