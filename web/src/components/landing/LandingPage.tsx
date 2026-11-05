import React from 'react'
import { Navigation } from './Navigation'
import { HeroSection } from './HeroSection'
import { BenchmarkFlowSection } from './BenchmarkFlow'
import { ProductShowcase } from './ProductShowcase'
import { FeatureBento } from './FeatureBento'
import { MetricsSection } from './MetricsSection'
import { PlatformSection } from './PlatformSection'
import { WaysToRun } from './WaysToRun'
import { Pillars } from './Pillars'
import { StackCards } from './StackCards'
import { RunAnywhere } from './RunAnywhere'
import { FAQSection } from './FAQSection'
import { FinalCTA } from './FinalCTA'
import { Footer } from './Footer'

import '../../styles/landing.css'

// The public site. It links out to GitHub and the docs only; the Workbench is a
// separate local app (`runport web`) and is never linked from here.
export const LandingPage: React.FC = () => (
  <div className="rp">
    <Navigation />
    <main>
      <HeroSection />
      <BenchmarkFlowSection />
      <ProductShowcase />
      <Pillars />
      <StackCards />
      <FeatureBento />
      <MetricsSection />
      <PlatformSection />
      <WaysToRun />
      <RunAnywhere />
      <FAQSection />
      <FinalCTA />
    </main>
    <Footer />
  </div>
)
