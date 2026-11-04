import React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { LANDING_CONTENT } from '../../data/landingContent'
import { EASE_OUT } from './motion'

// 64/600 statement, word-by-word blur rise as it enters the viewport.
export const StatementBanner: React.FC = () => {
  const c = LANDING_CONTENT.statement
  const reduce = useReducedMotion()
  const lead = c.lead.split(' ')
  const tail = c.tail.split(' ')

  const word = (w: string, i: number) => (
    <motion.span
      key={`${w}-${i}`}
      className="rp-word"
      variants={{
        hidden: reduce ? { opacity: 0 } : { opacity: 0, y: 24, filter: 'blur(10px)' },
        show: { opacity: 1, y: 0, filter: 'blur(0px)', transition: { duration: 0.8, ease: EASE_OUT } },
      }}
    >
      {w}{' '}
    </motion.span>
  )

  return (
    <section className="rp-statement" aria-label={`${c.lead} ${c.tail}`}>
      <motion.p
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: '0px 0px -15% 0px' }}
        variants={{ hidden: {}, show: { transition: { staggerChildren: reduce ? 0 : 0.06 } } }}
        aria-hidden="true"
      >
        {lead.map(word)}
        <br />
        {tail.map((w, i) => word(w, i + lead.length))}
      </motion.p>
    </section>
  )
}
