import React from 'react'
import { LANDING_CONTENT } from '../../data/landingContent'
import { Reveal } from './motionKit'
import { ProductWindow } from './graphics/ProductWindow'
import '../../styles/bento.css'

// Hero follow-through: a heading, then the large product window that settles
// flat as it scrolls into view.
export const ProductReveal: React.FC = () => {
  const c = LANDING_CONTENT.productWindow
  return (
    <section id="workbench" className="rp-section rp-pr" aria-labelledby="rp-pr-title">
      <Reveal className="rp-bento-head">
        <p className="rp-eyebrow">{c.eyebrow}</p>
        <h2 id="rp-pr-title" className="rp-h2 rp-fade-heading">
          {c.title}
        </h2>
        <p className="rp-body">{c.subheading}</p>
      </Reveal>
      <ProductWindow />
    </section>
  )
}
