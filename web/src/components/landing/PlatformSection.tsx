import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { ShieldCheck, Play, BarChart2 } from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'
import { EASE_OUT, Reveal } from './motion'

const PILLAR_ICONS = [ShieldCheck, Play, BarChart2]

// Reference: the hero painting returns full-bleed at 110%, fading into the
// canvas top and bottom, with a centred heading, a 3D mark and three pillars.
export const PlatformSection: React.FC = () => {
  const c = LANDING_CONTENT.platform
  const reduce = useReducedMotion()
  return (
    <section className="rp-platform" aria-label="Platform">
      <div className="rp-platform-art" aria-hidden="true">
        <img src="/assets/landing/hero-bg.png" alt="" loading="lazy" />
      </div>
      <Reveal className="rp-platform-head">
        <h2 className="rp-h2">{c.title}</h2>
        <p className="rp-body">{c.description}</p>
      </Reveal>
      <motion.div
        className="rp-mark"
        initial={reduce ? { opacity: 0 } : { opacity: 0, y: 30, scale: 0.94, filter: 'blur(10px)' }}
        whileInView={{ opacity: 1, y: 0, scale: 1, filter: 'blur(0px)' }}
        viewport={{ once: true, margin: '0px 0px -10% 0px' }}
        transition={{ duration: 1.1, ease: EASE_OUT }}
      >
        <img src="/assets/landing/runport-emblem.png" alt="Runport mark" />
      </motion.div>
      <div className="rp-pillars">
        {c.pillars.map((p, i) => {
          const Icon = PILLAR_ICONS[i]
          return (
            <Reveal key={p.title} className="rp-pillar" delay={0.08 * i}>
              <h3 className="rp-title"><Icon size={16} />{p.title}</h3>
              <p className="rp-body">{p.body}</p>
            </Reveal>
          )
        })}
      </div>
    </section>
  )
}
