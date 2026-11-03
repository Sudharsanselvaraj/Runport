import React, { useState } from 'react'
import { motion } from 'framer-motion'
import { Check, ArrowRight } from 'lucide-react'
import { LANDING_CONTENT, PricingPlan } from '../../data/landingContent'

interface PricingSectionProps {
  onLaunchWorkbench: () => void
}

export const PricingSection: React.FC<PricingSectionProps> = ({ onLaunchWorkbench }) => {
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')
  const content = LANDING_CONTENT.pricing

  return (
    <section id="pricing" className="rp-pricing-section">
      <div className="rp-container">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          style={{ maxWidth: '600px', margin: '0 auto' }}
        >
          <h2 className="rp-h2">
            Simple <span style={{ color: 'rgba(255, 255, 255, 0.65)' }}>pricing.</span>
          </h2>
          <p className="rp-body-muted" style={{ marginTop: '14px' }}>
            {content.subheading}
          </p>

          {/* Monthly / Yearly Toggle */}
          <div className="rp-pricing-toggle">
            <button
              onClick={() => setBillingCycle('monthly')}
              className={`rp-toggle-btn ${billingCycle === 'monthly' ? 'active' : ''}`}
            >
              Monthly
            </button>
            <button
              onClick={() => setBillingCycle('yearly')}
              className={`rp-toggle-btn ${billingCycle === 'yearly' ? 'active' : ''}`}
            >
              Yearly <span style={{ fontSize: '11px', opacity: 0.8 }}>(Save 20%)</span>
            </button>
          </div>
        </motion.div>

        {/* 3 Pricing Cards Grid */}
        <div className="rp-pricing-grid">
          {content.plans.map((plan: PricingPlan, idx: number) => {
            const price = billingCycle === 'monthly' ? plan.priceMonthly : plan.priceYearly

            return (
              <motion.div
                key={plan.id}
                initial={{ opacity: 0, y: 30 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.6, delay: idx * 0.1, ease: [0.16, 1, 0.3, 1] }}
                className={`rp-pricing-card ${plan.isFeatured ? 'featured' : ''}`}
              >
                <div>
                  {/* Price */}
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
                    <span style={{ fontFamily: 'var(--rp-font-display)', fontSize: '42px', fontWeight: 600, color: '#ffffff' }}>
                      ${price}
                    </span>
                    <span style={{ fontSize: '14px', color: 'rgba(255, 255, 255, 0.5)' }}>/ month</span>
                  </div>

                  {/* Plan Name & Description */}
                  <div style={{ fontSize: '18px', fontWeight: 600, color: '#ffffff', marginTop: '12px' }}>
                    {plan.name}
                  </div>
                  <p className="rp-body-muted" style={{ fontSize: '13.5px', marginTop: '6px', minHeight: '40px' }}>
                    {plan.description}
                  </p>

                  <hr style={{ borderColor: 'rgba(255, 255, 255, 0.08)', margin: '20px 0' }} />

                  {/* Feature Checklist */}
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {plan.features.map((feature: string) => (
                      <div key={feature} style={{ display: 'flex', alignItems: 'center', gap: '10px', fontSize: '13px' }}>
                        <Check size={14} style={{ color: '#10b981', flexShrink: 0 }} />
                        <span style={{ color: 'rgba(255, 255, 255, 0.85)' }}>{feature}</span>
                      </div>
                    ))}
                  </div>

                  {/* Visual Thumbnail */}
                  <img src={plan.imageBg} alt={plan.name} className="rp-plan-thumb" />
                </div>

                {/* CTA Button */}
                <div style={{ marginTop: '28px' }}>
                  <button
                    onClick={onLaunchWorkbench}
                    className={`rp-btn-pill ${plan.isFeatured ? 'rp-btn-solid-white' : 'rp-btn-glass'}`}
                    style={{ width: '100%', height: '42px' }}
                  >
                    <span>{plan.ctaText}</span>
                    <ArrowRight size={14} />
                  </button>
                </div>
              </motion.div>
            )
          })}
        </div>

        {/* Guarantee text */}
        <p className="rp-body-muted" style={{ marginTop: '36px', fontSize: '13px', letterSpacing: '0.02em' }}>
          {content.guarantee}
        </p>
      </div>
    </section>
  )
}
