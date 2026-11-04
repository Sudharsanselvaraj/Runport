import React, { useEffect, useRef, useState } from 'react'
import { animate, motion, useInView, useReducedMotion, type HTMLMotionProps } from 'framer-motion'

// Curves measured on the reference (see docs/landing-page-reference-audit.md §C):
// blur-rise entrances reach 50% at ~35% of an ~0.8s run.
export const EASE_OUT = [0.22, 1, 0.36, 1] as const
export const DUR = { fast: 0.25, base: 0.8, settle: 2.3 } as const

type RevealProps = HTMLMotionProps<'div'> & {
  delay?: number
  y?: number
  blur?: number
  once?: boolean
  as?: 'div' | 'section' | 'li'
}

/** Opacity / y / blur rise when scrolled into view (Framer "appear" equivalent). */
export const Reveal: React.FC<RevealProps> = ({ delay = 0, y = 40, blur = 10, once = true, as = 'div', children, ...rest }) => {
  const reduce = useReducedMotion()
  const Tag = motion[as] as typeof motion.div
  return (
    <Tag
      initial={reduce ? { opacity: 0 } : { opacity: 0, y, filter: `blur(${blur}px)` }}
      whileInView={reduce ? { opacity: 1 } : { opacity: 1, y: 0, filter: 'blur(0px)' }}
      viewport={{ once, margin: '0px 0px -12% 0px' }}
      transition={{ duration: reduce ? 0.2 : DUR.base, delay: reduce ? 0 : delay, ease: EASE_OUT }}
      {...rest}
    >
      {children}
    </Tag>
  )
}

/** Count a number up once it enters the viewport. */
export const CountUp: React.FC<{ value: number; decimals?: number; prefix?: string; suffix?: string; className?: string }> = ({
  value,
  decimals = 0,
  prefix = '',
  suffix = '',
  className,
}) => {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '0px 0px -10% 0px' })
  const reduce = useReducedMotion()
  const [shown, setShown] = useState(reduce ? value : 0)
  useEffect(() => {
    if (!inView || reduce) return
    // count from a few steps below so zeros still visibly "settle"
    const from = value === 0 ? 9 : 0
    const controls = animate(from, value, { duration: 1.1, ease: EASE_OUT, onUpdate: setShown })
    return () => controls.stop()
  }, [inView, reduce, value])
  return (
    <span ref={ref} className={className} aria-label={`${prefix}${value.toFixed(decimals)}${suffix}`}>
      {prefix}
      {shown.toFixed(decimals)}
      {suffix}
    </span>
  )
}

/** Scales a fixed-size canvas (e.g. a 680×700 product mockup) to its container width. */
export const ScaledCanvas: React.FC<{ width: number; height: number; className?: string; children: React.ReactNode }> = ({
  width,
  height,
  className,
  children,
}) => {
  const ref = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(1)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setScale(entry.contentRect.width / width))
    ro.observe(el)
    return () => ro.disconnect()
  }, [width])
  return (
    <div ref={ref} className={className} style={{ position: 'relative', width: '100%', height: height * scale, overflow: 'hidden' }}>
      <div style={{ width, height, transform: `scale(${scale})`, transformOrigin: '0 0', position: 'absolute', inset: 0 }}>{children}</div>
    </div>
  )
}
