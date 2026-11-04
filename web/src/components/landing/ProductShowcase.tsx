import React, { useRef, useState } from 'react'
import { AnimatePresence, motion, useMotionValueEvent, useReducedMotion, useScroll } from 'framer-motion'
import { LANDING_CONTENT } from '../../data/landingContent'
import { RunportMockup, MOCKUP_SIZE } from './RunportMockups'
import { EASE_OUT, Reveal, ScaledCanvas } from './motion'

// Sticky scroll scene (reference: header pins at top 40 for the length of the
// track; the step advances every ~100px (track: 100vh + 400px) of scroll and both the card copy and the
// product mockup crossfade).
const STEP_PX = 100

export const ProductShowcase: React.FC = () => {
  const c = LANDING_CONTENT.showcase
  const trackRef = useRef<HTMLDivElement>(null)
  const [step, setStep] = useState(0)
  const reduce = useReducedMotion()
  const { scrollYProgress } = useScroll({ target: trackRef, offset: ['start start', 'end end'] })

  useMotionValueEvent(scrollYProgress, 'change', (p) => {
    const next = Math.min(c.steps.length - 1, Math.max(0, Math.floor(p * c.steps.length * 0.999)))
    setStep((s) => (s === next ? s : next))
  })

  const goTo = (i: number) => {
    const el = trackRef.current
    if (!el) return
    const top = el.getBoundingClientRect().top + window.scrollY
    window.scrollTo({ top: top + i * STEP_PX + 8, behavior: reduce ? 'auto' : 'smooth' })
  }

  const fade = reduce
    ? { initial: { opacity: 0 }, animate: { opacity: 1 }, exit: { opacity: 0 }, transition: { duration: 0.15 } }
    : {
        initial: { opacity: 0, y: 12, filter: 'blur(6px)' },
        animate: { opacity: 1, y: 0, filter: 'blur(0px)' },
        exit: { opacity: 0, y: -12, filter: 'blur(6px)' },
        transition: { duration: 0.45, ease: EASE_OUT },
      }

  const current = c.steps[step]

  const head = (
    <div className="rp-showcase-head">
      <h2 className="rp-h1 rp-fade-heading">
        {c.titleA}
        <br />
        {c.titleB}
      </h2>
      <p className="rp-body">{c.aside}</p>
    </div>
  )

  return (
    <section id="product" className="rp-showcase">
      <div className="rp-glow" aria-hidden="true">
        <img src="/assets/landing/hero-bg.png" alt="" />
      </div>

      {/* desktop / tablet: pinned stage */}
      <div ref={trackRef} className="rp-showcase-track">
        <div className="rp-showcase-stage">
          <div className="rp-col">
            <Reveal>{head}</Reveal>
            <Reveal className="rp-showcase-grid" delay={0.1}>
              <div className="rp-step-card rp-glass-card">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.div key={step} className="rp-step-inner" {...fade}>
                    <span className="rp-tag">{current.tag}</span>
                    <div className="rp-step-copy">
                      <h3 className="rp-h3">{current.title}</h3>
                      <p className="rp-body">{current.body}</p>
                    </div>
                  </motion.div>
                </AnimatePresence>
                <div className="rp-step-dots" role="tablist" aria-label="Benchmark lifecycle">
                  {c.steps.map((s, i) => (
                    <button
                      key={s.tag}
                      type="button"
                      role="tab"
                      aria-selected={i === step}
                      className={`rp-step-dot${i === step ? ' is-active' : ''}`}
                      onClick={() => goTo(i)}
                    >
                      <i />
                      {s.tag.replace(/\s+/, ' ')}
                    </button>
                  ))}
                </div>
              </div>
              <div className="rp-mock-frame">
                <AnimatePresence initial={false}>
                  <motion.div
                    key={step}
                    className="rp-mock-layer"
                    initial={{ opacity: 0, scale: reduce ? 1 : 1.015 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: reduce ? 0.15 : 0.5, ease: EASE_OUT }}
                  >
                    <ScaledCanvas width={MOCKUP_SIZE.width} height={MOCKUP_SIZE.height}>
                      <RunportMockup kind={current.mockup} />
                    </ScaledCanvas>
                  </motion.div>
                </AnimatePresence>
              </div>
            </Reveal>
          </div>
        </div>
      </div>

      {/* phone: the same four steps, stacked */}
      <div className="rp-showcase-mobile">
        <Reveal>{head}</Reveal>
        {c.steps.map((s) => (
          <Reveal key={s.tag} className="rp-step-m rp-glass-card">
            <span className="rp-tag" style={{ alignSelf: 'flex-start' }}>{s.tag}</span>
            <div className="rp-step-copy">
              <h3 className="rp-h3">{s.title}</h3>
              <p className="rp-body">{s.body}</p>
            </div>
            <ScaledCanvas width={MOCKUP_SIZE.width} height={MOCKUP_SIZE.height * 0.72}>
              <RunportMockup kind={s.mockup} />
            </ScaledCanvas>
          </Reveal>
        ))}
      </div>
    </section>
  )
}
