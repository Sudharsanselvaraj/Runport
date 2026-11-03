import React from 'react'
import { Navigation } from './Navigation'
import { HeroSection } from './HeroSection'
import { StatementBanner } from './StatementBanner'
import { InterfaceShowcase } from './InterfaceShowcase'
import { BentoGrid } from './BentoGrid'
import { MetricsSection } from './MetricsSection'
import { BrandShowcase } from './BrandShowcase'
import { PricingSection } from './PricingSection'
import { FAQSection } from './FAQSection'
import { FinalCTA } from './FinalCTA'
import { Footer } from './Footer'

import '../../styles/landing.css'

interface LandingPageProps {
  onLaunchWorkbench: () => void
}

export const LandingPage: React.FC<LandingPageProps> = ({ onLaunchWorkbench }) => {
  return (
    <div className="rp-landing-wrapper">
      <Navigation onLaunchWorkbench={onLaunchWorkbench} />
      <main>
        <HeroSection onLaunchWorkbench={onLaunchWorkbench} />
        <StatementBanner />
        <InterfaceShowcase />
        <BentoGrid />
        <MetricsSection />
        <BrandShowcase />
        <PricingSection onLaunchWorkbench={onLaunchWorkbench} />
        <FAQSection />
        <FinalCTA onLaunchWorkbench={onLaunchWorkbench} />
      </main>
      <Footer onLaunchWorkbench={onLaunchWorkbench} />
    </div>
  )
}
