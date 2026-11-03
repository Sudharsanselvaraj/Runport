import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ChevronDown, MessageSquare } from 'lucide-react'
import { LANDING_CONTENT, FAQItem } from '../../data/landingContent'

export const FAQSection: React.FC = () => {
  const [openId, setOpenId] = useState<string | null>('faq-1')
  const content = LANDING_CONTENT.faq

  const toggleItem = (id: string) => {
    setOpenId((prev) => (prev === id ? null : id))
  }

  return (
    <section className="rp-faq-section">
      <div className="rp-container">
        <div className="rp-faq-grid">
          {/* Left Column */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6 }}
          >
            <h2 className="rp-h2">
              Questions, <span style={{ color: 'rgba(255, 255, 255, 0.55)' }}>answered.</span>
            </h2>
            <p className="rp-body-muted" style={{ marginTop: '14px', maxWidth: '300px' }}>
              {content.subheading}
            </p>

            <div style={{ marginTop: '48px' }}>
              <div style={{ fontSize: '14px', color: 'rgba(255, 255, 255, 0.45)', marginBottom: '14px' }}>
                {content.ctaPrompt}
              </div>
              <a
                href="https://github.com/Sudharsanselvaraj/runport/issues"
                target="_blank"
                rel="noopener noreferrer"
                className="rp-btn-pill rp-btn-glass"
                style={{ height: '38px', padding: '0 18px', fontSize: '13px' }}
              >
                <MessageSquare size={13} />
                <span>{content.ctaButton}</span>
              </a>
            </div>
          </motion.div>

          {/* Right Column: Accordion */}
          <div className="rp-faq-accordion">
            {content.items.map((item: FAQItem) => {
              const isOpen = openId === item.id

              return (
                <div key={item.id} className="rp-faq-item">
                  <button onClick={() => toggleItem(item.id)} className="rp-faq-trigger">
                    <span>{item.question}</span>
                    <motion.div animate={{ rotate: isOpen ? 180 : 0 }} transition={{ duration: 0.2 }}>
                      <ChevronDown size={18} style={{ opacity: 0.6 }} />
                    </motion.div>
                  </button>

                  <AnimatePresence>
                    {isOpen && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                        style={{ overflow: 'hidden' }}
                      >
                        <div className="rp-faq-content">{item.answer}</div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </section>
  )
}
