import React from 'react'
import { motion } from 'framer-motion'
import { Cpu, Layers, Wallet, ShieldCheck, ArrowUpRight } from 'lucide-react'
import { LANDING_CONTENT, BentoCardItem } from '../../data/landingContent'

export const BentoGrid: React.FC = () => {
  const content = LANDING_CONTENT.bentoGrid

  const renderIcon = (name: string) => {
    switch (name) {
      case 'Cpu':
        return <Cpu size={20} style={{ color: '#f59e0b' }} />
      case 'Layers':
        return <Layers size={20} style={{ color: '#3b82f6' }} />
      case 'Wallet':
        return <Wallet size={20} style={{ color: '#10b981' }} />
      case 'ShieldCheck':
      default:
        return <ShieldCheck size={20} style={{ color: '#06b6d4' }} />
    }
  }

  const renderMiniPreview = (type: BentoCardItem['previewType']) => {
    switch (type) {
      case 'models':
        return (
          <div
            style={{
              padding: '16px',
              borderRadius: '12px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              marginBottom: '20px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)', marginBottom: '8px' }}>
              <span>Candidate Model</span>
              <span>Rate / 1M</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#fff', marginBottom: '6px' }}>
              <span>Gemini 3.5 Flash</span>
              <span style={{ color: '#f59e0b' }}>$0.15</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: 'rgba(255, 255, 255, 0.7)' }}>
              <span>Claude 3.5 Haiku</span>
              <span style={{ color: '#f59e0b' }}>$0.80</span>
            </div>
          </div>
        )

      case 'workflows':
        return (
          <div
            style={{
              padding: '16px',
              borderRadius: '12px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              marginBottom: '20px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#3b82f6' }} />
              <span style={{ fontSize: '12px', color: '#fff', fontWeight: 500 }}>Dify Workflow App</span>
            </div>
            <div style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)', fontFamily: 'var(--rp-font-mono)' }}>
              POST /v1/workflows/run
            </div>
          </div>
        )

      case 'budget':
        return (
          <div
            style={{
              padding: '16px',
              borderRadius: '12px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              marginBottom: '20px',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '4px' }}>
              <span style={{ color: 'rgba(255, 255, 255, 0.6)' }}>Hard Ceiling</span>
              <span style={{ color: '#10b981', fontWeight: 600 }}>$5.00</span>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)' }}>
              <span>Per-case Cap</span>
              <span>$0.05 max</span>
            </div>
          </div>
        )

      case 'approval':
      default:
        return (
          <div
            style={{
              padding: '16px',
              borderRadius: '12px',
              background: 'rgba(255, 255, 255, 0.03)',
              border: '1px solid rgba(255, 255, 255, 0.06)',
              marginBottom: '20px',
            }}
          >
            <div style={{ fontSize: '11px', color: 'rgba(255, 255, 255, 0.4)', marginBottom: '4px' }}>SHA-256 Plan Hash</div>
            <div style={{ fontSize: '11px', color: '#06b6d4', fontFamily: 'var(--rp-font-mono)', wordBreak: 'break-all' }}>
              9a2b8e...3d17f4c0
            </div>
          </div>
        )
    }
  }

  return (
    <section id="workflows" className="rp-bento-section">
      <div className="rp-container">
        {/* Title */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          style={{ textAlign: 'center', maxWidth: '640px', margin: '0 auto' }}
        >
          <h2 className="rp-h2">{content.heading}</h2>
          <p className="rp-body-muted" style={{ marginTop: '14px' }}>
            {content.subheading}
          </p>
        </motion.div>

        {/* 4 Cards Grid */}
        <div className="rp-bento-grid">
          {content.cards.map((card, idx) => (
            <motion.div
              key={card.id}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.6, delay: idx * 0.1, ease: [0.16, 1, 0.3, 1] }}
              className="rp-bento-card"
            >
              {/* Tinted Ambient Glow Orb */}
              <div className="rp-bento-glow" style={{ background: card.glowColor }} />

              {/* Card Top: Preview + Icon */}
              <div className="rp-bento-content">
                {renderMiniPreview(card.previewType)}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
                  {renderIcon(card.iconName)}
                  <span style={{ fontSize: '12px', fontWeight: 500, color: 'rgba(255, 255, 255, 0.5)', textTransform: 'uppercase' }}>
                    {card.tag}
                  </span>
                </div>
                <h3 style={{ fontSize: '19px', fontWeight: 600, color: '#ffffff', marginBottom: '10px', lineHeight: 1.3 }}>
                  {card.title}
                </h3>
              </div>

              {/* Card Bottom: Description */}
              <div className="rp-bento-content">
                <p className="rp-body-muted" style={{ fontSize: '13.5px', lineHeight: 1.55 }}>
                  {card.description}
                </p>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  )
}
