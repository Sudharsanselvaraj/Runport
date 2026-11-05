import React, { createContext, useContext, useEffect, useRef, useState } from 'react'
import { motion, useReducedMotion, type HTMLMotionProps } from 'framer-motion'

// Reusable motion pieces for the bento section and the product window.
// - Loops run only while their element is on screen, the tab is visible, the
//   reader has not paused them, and reduced motion is off.
// - Everything animates transform and opacity only.

export const EASE = [0.22, 1, 0.36, 1] as const

/** Section-level pause for every loop inside it (WCAG 2.2.2 pause control). */
const PauseContext = createContext<{ paused: boolean; setPaused: (p: boolean) => void }>({ paused: false, setPaused: () => undefined })

export const MotionPauseProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [paused, setPaused] = useState(false)
  return <PauseContext.Provider value={{ paused, setPaused }}>{children}</PauseContext.Provider>
}

export const useMotionPause = () => useContext(PauseContext)

function usePageVisible() {
  const [visible, setVisible] = useState(() => (typeof document === 'undefined' ? true : !document.hidden))
  useEffect(() => {
    const on = () => setVisible(!document.hidden)
    document.addEventListener('visibilitychange', on)
    return () => document.removeEventListener('visibilitychange', on)
  }, [])
  return visible
}

function useOnScreen(ref: React.RefObject<Element>, rootMargin = '0px') {
  const [on, setOn] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || typeof IntersectionObserver === 'undefined') return
    const io = new IntersectionObserver(([e]) => setOn(e.isIntersecting), { rootMargin })
    io.observe(el)
    return () => io.disconnect()
  }, [ref, rootMargin])
  return on
}

/** True while a loop should run: on screen, tab visible, not paused, motion allowed. */
export function useLoopWhenVisible(ref: React.RefObject<Element>): { active: boolean; reduced: boolean } {
  const reduced = !!useReducedMotion()
  const onScreen = useOnScreen(ref)
  const visible = usePageVisible()
  const { paused } = useMotionPause()
  return { active: onScreen && visible && !paused && !reduced, reduced }
}

/** Render-prop form of useLoopWhenVisible. */
export const LoopWhenVisible: React.FC<{ className?: string; children: (s: { active: boolean; reduced: boolean }) => React.ReactNode }> = ({ className, children }) => {
  const ref = useRef<HTMLDivElement>(null)
  const state = useLoopWhenVisible(ref)
  return (
    <div ref={ref} className={className}>
      {children(state)}
    </div>
  )
}

/**
 * Seconds of loop time, advancing only while `active`. `step` throttles React
 * updates (seconds between renders); time resumes where it paused.
 */
export function useLoopClock(active: boolean, step = 0.25): number {
  const [t, setT] = useState(0)
  const acc = useRef(0)
  useEffect(() => {
    if (!active) return
    let raf = 0
    let last = performance.now()
    let lastEmit = 0
    const tick = (now: number) => {
      acc.current += (now - last) / 1000
      last = now
      if (acc.current - lastEmit >= step) {
        lastEmit = acc.current
        setT(acc.current)
      }
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [active, step])
  return t
}

/** rAF callback with loop time in seconds, for per-frame transforms written straight to the DOM. */
export function useRafLoop(active: boolean, cb: (tSec: number) => void) {
  const acc = useRef(0)
  const cbRef = useRef(cb)
  cbRef.current = cb
  useEffect(() => {
    cbRef.current(acc.current)
    if (!active) return
    let raf = 0
    let last = performance.now()
    const tick = (now: number) => {
      acc.current += Math.min(0.1, (now - last) / 1000)
      last = now
      cbRef.current(acc.current)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [active])
}

/** Fade + 20px rise, 600ms, staggered 80ms by index. Reduced motion: no movement. */
export const Reveal: React.FC<{ index?: number; className?: string; children: React.ReactNode } & Omit<HTMLMotionProps<'div'>, 'children'>> = ({
  index = 0,
  className,
  children,
  ...rest
}) => {
  const reduced = useReducedMotion()
  return (
    <motion.div
      className={className}
      initial={reduced ? false : { opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '0px 0px -10% 0px' }}
      transition={{ duration: 0.6, delay: reduced ? 0 : index * 0.08, ease: EASE }}
      {...rest}
    >
      {children}
    </motion.div>
  )
}

const finePointer = () => typeof window !== 'undefined' && window.matchMedia('(hover: hover) and (pointer: fine)').matches

/**
 * Sets --px and --py (-1..1) from the pointer position over the element, for
 * children that translate by `calc(var(--px) * Npx)`. Off for reduced motion and
 * touch screens.
 */
export const PointerParallax: React.FC<{ className?: string; children: React.ReactNode }> = ({ className, children }) => {
  const reduced = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (reduced || !finePointer()) return
    const r = e.currentTarget.getBoundingClientRect()
    e.currentTarget.style.setProperty('--px', (((e.clientX - r.left) / r.width) * 2 - 1).toFixed(3))
    e.currentTarget.style.setProperty('--py', (((e.clientY - r.top) / r.height) * 2 - 1).toFixed(3))
  }
  const onLeave = () => {
    ref.current?.style.setProperty('--px', '0')
    ref.current?.style.setProperty('--py', '0')
  }
  return (
    <div ref={ref} className={`rp-parallax${className ? ` ${className}` : ''}`} onPointerMove={onMove} onPointerLeave={onLeave}>
      {children}
    </div>
  )
}

/**
 * A bento card. Hover only brightens the border and shows a soft spotlight that
 * follows the cursor (CSS variables). The card itself never moves, scales or
 * tilts, so cards in a row keep identical top edges. It fades in (opacity only).
 */
export const BentoCard: React.FC<{ className?: string; index?: number; children: React.ReactNode; labelledBy?: string }> = ({ className, index = 0, children, labelledBy }) => {
  const reduced = useReducedMotion()
  const onMove = (e: React.PointerEvent<HTMLElement>) => {
    const el = e.currentTarget
    const r = el.getBoundingClientRect()
    el.style.setProperty('--mx', `${(((e.clientX - r.left) / r.width) * 100).toFixed(1)}%`)
    el.style.setProperty('--my', `${(((e.clientY - r.top) / r.height) * 100).toFixed(1)}%`)
  }
  return (
    <motion.div
      className={`rp-bento-cell ${className ?? ''}`}
      initial={reduced ? false : { opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true, margin: '0px 0px -10% 0px' }}
      transition={{ duration: 0.6, delay: reduced ? 0 : index * 0.08, ease: EASE }}
    >
      <article className="rp-bento-card" onPointerMove={onMove} aria-labelledby={labelledBy}>
        <span className="rp-bento-spot" aria-hidden="true" />
        {children}
      </article>
    </motion.div>
  )
}
