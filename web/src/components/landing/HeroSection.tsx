import React, { useRef } from 'react'
import { motion, useReducedMotion, useScroll, useTransform } from 'framer-motion'
import { LANDING_CONTENT } from '../../data/landingContent'
import { DUR, EASE_OUT } from './motion'

// Measured entrance: copy rises 40px from blur(10px) over ~0.8s starting ~0.5s
// after first paint, sub +0.12s; the painting settles from -45px over ~2.3s and
// then scrolls at 0.7x (parallax).
const START = 0.45

const newTab = (href: string) => (/^https?:/.test(href) ? { target: '_blank', rel: 'noopener noreferrer' } : {})

export const HeroSection: React.FC = () => {
  const c = LANDING_CONTENT.hero
  const ref = useRef<HTMLElement>(null)
  const reduce = useReducedMotion()
  const { scrollY } = useScroll()
  const parallax = useTransform(scrollY, (v) => (reduce ? 0 : v * 0.3))

  const rise = (delay: number, y = 40, blur = 10) =>
    reduce
      ? { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.2 } }
      : {
          initial: { opacity: 0, y, filter: `blur(${blur}px)` },
          animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
          transition: { duration: DUR.base, delay: START + delay, ease: EASE_OUT },
        }

  return (
    <section id="top" ref={ref} className="rp-hero">
      <motion.div className="rp-hero-art" style={{ y: parallax }}>
        <motion.img
          src="/assets/landing/hero-bg.png"
          alt=""
          initial={reduce ? false : { y: -45, scale: 1.04 }}
          animate={{ y: 0, scale: 1 }}
          transition={{ duration: DUR.settle, ease: EASE_OUT }}
        />
      </motion.div>
      <div className="rp-hero-shade" />

      <div className="rp-hero-copy">
        <motion.h1 className="rp-h1" {...rise(0)}>
          {c.title}
        </motion.h1>
        <motion.p className="rp-body" {...rise(0.12)}>
          {c.description}
        </motion.p>
        <motion.div className="rp-hero-actions" {...rise(0, 40, 0)}>
          <a href={c.ctaPrimaryHref} {...newTab(c.ctaPrimaryHref)} className="rp-pill rp-pill-glass">
            {c.ctaPrimary}
          </a>
          <a href="#product" className="rp-pill rp-pill-dark">
            {c.ctaSecondary}
          </a>
        </motion.div>
      </div>

      <motion.div className="rp-hero-foot" {...rise(0.4, 20, 0)}>
        <p className="rp-body">{c.marqueeLabel}</p>
        <div className="rp-marquee" aria-label={c.marquee.join(', ')}>
          <div className="rp-marquee-track" aria-hidden="true">
            {[...c.marquee, ...c.marquee].map((name, i) => (
              // style keyed to the name's position in the original list so the
              // duplicated half loops seamlessly
              <span key={i} className={`rp-wm rp-wm-${(i % c.marquee.length) % 4}`}>
                {name}
              </span>
            ))}
          </div>
        </div>
      </motion.div>
    </section>
  )
}
