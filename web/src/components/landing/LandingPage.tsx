import React from 'react'
import { Navigation } from './Navigation'
import { HeroSection } from './HeroSection'
import { StatementBanner } from './StatementBanner'
import { StackFlow } from './StackFlow'
import { ProductShowcase } from './ProductShowcase'
import { FeatureCarousel } from './FeatureCarousel'
import { MetricsSection } from './MetricsSection'
import { PlatformSection } from './PlatformSection'
import { WaysToRun } from './WaysToRun'
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
      <StatementBanner />
      <StackFlow />
      <ProductShowcase />
      <FeatureCarousel />
      <MetricsSection />
      <PlatformSection />
      <WaysToRun />
      <FAQSection />
      <FinalCTA />
    </main>
    <Footer />
  </div>
)
