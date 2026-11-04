import React, { useState } from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { Terminal, Monitor, Folder, FileText, ShieldCheck, GitBranch, type LucideIcon } from 'lucide-react'
import { LANDING_CONTENT, type FeatureIcon } from '../../data/landingContent'
import { EASE_OUT, Reveal } from './motion'

export const FEATURE_ICONS: Record<FeatureIcon, LucideIcon> = {
  terminal: Terminal, monitor: Monitor, folder: Folder, file: FileText, shield: ShieldCheck, git: GitBranch,
}

// Runport is Apache-2.0, so every plan is $0. The toggle switches between
// replay and live runs and shows what each costs in provider spend.
export const PricingSection: React.FC = () => {
  const c = LANDING_CONTENT.pricing
  const [mode, setMode] = useState<(typeof c.toggle)[number]>('Replay')
  const reduce = useReducedMotion()

  return (
    <section id="pricing" className="rp-section">
      <div className="rp-col">
        <Reveal className="rp-pricing-head">
          <h2 className="rp-h2 rp-fade-heading">
            {c.titleA} {c.titleB}
          </h2>
          <p className="rp-body">{c.subheading}</p>
        </Reveal>

        <Reveal style={{ display: 'flex' }} delay={0.05}>
          <div className="rp-toggle" role="radiogroup" aria-label="Run mode">
            {c.toggle.map((m) => (
              <button key={m} type="button" role="radio" aria-checked={mode === m} className={mode === m ? 'is-active' : ''} onClick={() => setMode(m)}>
                {mode === m && (
                  <motion.span layoutId="rp-toggle-thumb" className="rp-toggle-thumb" transition={reduce ? { duration: 0 } : { type: 'spring', stiffness: 420, damping: 36 }} />
                )}
                <span style={{ position: 'relative' }}>{m}</span>
              </button>
            ))}
          </div>
        </Reveal>

        <div className="rp-plans">
          {c.plans.map((plan, i) => (
            <Reveal key={plan.id} className="rp-plan rp-glass-card" delay={0.08 * i}>
              <div className="rp-plan-top">
                <span className="rp-tag" style={{ alignSelf: 'flex-start' }}>{plan.tag}</span>
                <div>
                  <div className="rp-price">
                    <b>{plan.price}</b>
                    <span className="rp-body">{plan.unit}</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    <p className="rp-body">{plan.description}</p>
                    <AnimatePresence mode="wait" initial={false}>
                      <motion.p
                        key={mode}
                        className="rp-caption"
                        style={{ color: 'var(--rp-muted)' }}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -4 }}
                        transition={{ duration: 0.25, ease: EASE_OUT }}
                      >
                        {c.spendNote[mode]}
                      </motion.p>
                    </AnimatePresence>
                  </div>
                </div>
              </div>
              <div className="rp-plan-media">
                <img src={plan.image} alt="" loading="lazy" />
                <ul>
                  {plan.features.map((f) => {
                    const Icon = FEATURE_ICONS[f.icon]
                    return (
                      <li key={f.label}>
                        <Icon size={15} />
                        {f.label}
                      </li>
                    )
                  })}
                </ul>
              </div>
            </Reveal>
          ))}
        </div>
        <p className="rp-caption rp-pricing-note">{c.footnote}</p>
      </div>
    </section>
  )
}
