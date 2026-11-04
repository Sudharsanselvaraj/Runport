import React, { useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Plus } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'
import { EASE_OUT, Reveal } from './motion'

export const FAQSection: React.FC = () => {
  const c = LANDING_CONTENT.faq
  const [open, setOpen] = useState<string | null>(null)
  const reduce = useReducedMotion()

  return (
    <section id="faq" className="rp-section">
      <div className="rp-col rp-faq-grid">
        <Reveal className="rp-faq-side">
          <div>
            <h2 className="rp-h2 rp-fade-heading">
              {c.titleA} {c.titleB}
            </h2>
            <p className="rp-body">{c.subheading}</p>
          </div>
          <div className="rp-faq-cta">
            <p className="rp-body" style={{ fontWeight: 500 }}>{c.ctaPrompt}</p>
            <a href={c.ctaHref} target="_blank" rel="noopener noreferrer" className="rp-pill rp-pill-sm rp-pill-glass">
              {c.ctaButton}
            </a>
          </div>
        </Reveal>

        <div className="rp-faq-list">
          {c.items.map((item, i) => {
            const isOpen = open === item.id
            return (
              <Reveal key={item.id} delay={0.05 * i} className={`rp-faq-item${isOpen ? ' is-open' : ''}`}>
                <button
                  type="button"
                  className="rp-faq-q"
                  aria-expanded={isOpen}
                  aria-controls={`faq-${item.id}`}
                  onClick={() => setOpen(isOpen ? null : item.id)}
                >
                  {item.question}
                  <Plus size={16} />
                </button>
                <AnimatePresence initial={false}>
                  {isOpen && (
                    <motion.div
                      id={`faq-${item.id}`}
                      key="a"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: reduce ? 0 : 0.35, ease: EASE_OUT }}
                      style={{ overflow: 'hidden' }}
                    >
                      <p className="rp-body rp-faq-a">{item.answer}</p>
                    </motion.div>
                  )}
                </AnimatePresence>
              </Reveal>
            )
          })}
        </div>
      </div>
    </section>
  )
}
