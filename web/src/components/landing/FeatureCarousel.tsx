import React, { useCallback, useEffect, useRef, useState } from 'react'
import { animate, motion, useMotionValue, useReducedMotion } from 'framer-motion'
import { Cpu, Database, Workflow, Wallet, Activity, GitCompare, type LucideIcon } from 'lucide-react'
import { LANDING_CONTENT, type CarouselCard } from '../../data/landingContent'
import { RunportMockup, MOCKUP_SIZE } from './RunportMockups'
import { EASE_OUT, Reveal, ScaledCanvas } from './motion'

const ICONS: Record<CarouselCard['icon'], LucideIcon> = {
  cpu: Cpu, database: Database, workflow: Workflow, wallet: Wallet, activity: Activity, 'git-compare': GitCompare,
}

// Reference: 282 × 355 tiles, 16px gap, draggable track with page dots.
export const FeatureCarousel: React.FC = () => {
  const c = LANDING_CONTENT.carousel
  const viewportRef = useRef<HTMLDivElement>(null)
  const trackRef = useRef<HTMLDivElement>(null)
  const x = useMotionValue(0)
  const reduce = useReducedMotion()
  const [pages, setPages] = useState<number[]>([0])
  const [page, setPage] = useState(0)

  const measure = useCallback(() => {
    const vp = viewportRef.current
    const tr = trackRef.current
    if (!vp || !tr) return
    const max = Math.max(0, tr.scrollWidth - vp.clientWidth)
    const count = max === 0 ? 1 : Math.max(2, Math.ceil(max / (vp.clientWidth * 0.75)) + 1)
    setPages(Array.from({ length: count }, (_, i) => (count === 1 ? 0 : -(max * i) / (count - 1))))
  }, [])

  useEffect(() => {
    measure()
    const ro = new ResizeObserver(measure)
    if (viewportRef.current) ro.observe(viewportRef.current)
    return () => ro.disconnect()
  }, [measure])

  const snapTo = (i: number) => {
    const idx = Math.max(0, Math.min(pages.length - 1, i))
    setPage(idx)
    animate(x, pages[idx], reduce ? { duration: 0 } : { type: 'spring', stiffness: 260, damping: 34 })
  }

  const minX = pages[pages.length - 1] ?? 0

  return (
    <section id="features" className="rp-section">
      <div className="rp-col">
        <Reveal className="rp-carousel-head">
          <h2 className="rp-h2 rp-fade-heading">
            {c.titleA}
            <br />
            {c.titleB}
          </h2>
        </Reveal>
      </div>
      <Reveal delay={0.1}>
        <div ref={viewportRef} className="rp-carousel-viewport">
          <motion.div
            ref={trackRef}
            className="rp-carousel-track"
            style={{ x, paddingLeft: 'max(var(--rp-gutter), calc((100vw - var(--rp-col)) / 2))' }}
            drag="x"
            dragConstraints={{ left: minX, right: 0 }}
            dragElastic={0.08}
            onDragEnd={(_, info) => {
              const projected = x.get() + info.velocity.x * 0.2
              let best = 0
              pages.forEach((p, i) => { if (Math.abs(p - projected) < Math.abs(pages[best] - projected)) best = i })
              snapTo(best)
            }}
          >
            {c.cards.map((card, i) => {
              const Icon = ICONS[card.icon]
              return (
                <motion.article
                  key={card.title}
                  className={`rp-tile rp-tile-${card.tint}`}
                  initial={reduce ? { opacity: 0 } : { opacity: 0, y: 40, filter: 'blur(10px)' }}
                  whileInView={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                  viewport={{ once: true, margin: '0px 0px -10% 0px' }}
                  transition={{ duration: 0.8, delay: reduce ? 0 : 0.08 * i, ease: EASE_OUT }}
                >
                  <div className="rp-tile-media">
                    <ScaledCanvas width={MOCKUP_SIZE.width} height={MOCKUP_SIZE.height}>
                      <RunportMockup kind={card.mockup} />
                    </ScaledCanvas>
                  </div>
                  <h3 className="rp-title rp-tile-title"><Icon size={16} />{card.title}</h3>
                  <p className="rp-body">{card.body}</p>
                </motion.article>
              )
            })}
          </motion.div>
        </div>
        {pages.length > 1 && (
          <div className="rp-dots" role="tablist" aria-label="Feature pages">
            {pages.map((_, i) => (
              <button key={i} type="button" role="tab" aria-selected={i === page} aria-label={`Page ${i + 1}`} className={i === page ? 'is-active' : ''} onClick={() => snapTo(i)} />
            ))}
          </div>
        )}
      </Reveal>
    </section>
  )
}
