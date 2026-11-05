import React, { Suspense, lazy } from 'react'
import { Navigation } from './Navigation'
import { HeroSection } from './HeroSection'
import { BenchmarkFlowSection } from './BenchmarkFlow'
import { ProductShowcase } from './ProductShowcase'
import { MetricsSection } from './MetricsSection'
import { Pillars } from './Pillars'
import { StackCards } from './StackCards'
import { RunAnywhere } from './RunAnywhere'
import { FAQSection } from './FAQSection'
import { FinalCTA } from './FinalCTA'
import { Footer } from './Footer'

import '../../styles/landing.css'

// The product window and the bento section load as separate chunks. Their
// placeholders reserve height so nothing below them shifts.
const ProductReveal = lazy(() => import('./ProductReveal').then((m) => ({ default: m.ProductReveal })))
const BentoSection = lazy(() => import('./BentoSection').then((m) => ({ default: m.BentoSection })))

// The public site. It links out to GitHub and the docs only; the Workbench is a
// separate local app (`runport web`) and is never linked from here.
export const LandingPage: React.FC = () => (
  <div className="rp">
    <Navigation />
    <main>
      <HeroSection />
      <Suspense fallback={<div className="rp-lazy rp-lazy-pr" aria-hidden="true" />}>
        <ProductReveal />
      </Suspense>
      <BenchmarkFlowSection />
      <ProductShowcase />
      <Pillars />
      <StackCards />
      <Suspense fallback={<div className="rp-lazy rp-lazy-bento" aria-hidden="true" />}>
        <BentoSection />
      </Suspense>
      <MetricsSection />
      <RunAnywhere />
      <FAQSection />
      <FinalCTA />
    </main>
    <Footer />
  </div>
)
