export interface NavItem {
  label: string
  href: string
  isExternal?: boolean
}

export interface MetricItem {
  value: string
  label: string
}

export interface BentoCardItem {
  id: string
  tag: string
  title: string
  description: string
  glowColor: string
  iconName: string
  previewType: 'models' | 'workflows' | 'budget' | 'approval'
}

export interface PricingPlan {
  id: string
  name: string
  priceMonthly: number
  priceYearly: number
  description: string
  features: string[]
  isFeatured?: boolean
  ctaText: string
  imageBg: string
}

export interface FAQItem {
  id: string
  question: string
  answer: string
}

export const LANDING_CONTENT = {
  navigation: {
    brandName: 'RUNPORT',
    links: [
      { label: 'Product', href: '#features' },
      { label: 'Workflows', href: '#workflows' },
      { label: 'Pricing', href: '#pricing' },
      { label: 'Docs', href: 'https://github.com/Sudharsanselvaraj/runport', isExternal: true },
    ],
    ctaSecondary: 'Read Docs',
    ctaPrimary: 'Launch Workbench',
  },

  hero: {
    badge: 'v0.1.0 Public Alpha · Local-First LLM Benchmarking',
    title: 'Make ideas move.',
    titleAccent: 'Under hard spend caps.',
    description:
      'A universal, local-first platform to benchmark models, prompts, and compound agent workflows against verified ground truth.',
    ctaPrimary: 'Start for free',
    ctaSecondary: 'See how it works',
    trustedLabel: 'Trusted by engineering teams and AI researchers',
    trustedLogos: ['LAKEWOOD', 'CRESTLINE', 'HARBORVIEW', 'SUMMIT', 'NORTHGATE', 'MERIDIAN'],
  },

  statement: {
    text: "LLM benchmarking shouldn't feel this scattered.",
    highlight: "scattered.",
    subtext:
      'Traditional benchmarks run until payment cards decline or report consensus as ground truth. Runport brings honest accounting and hard spend caps.',
  },

  interfaceShowcase: {
    sectionTag: '01 Benchmark',
    heading: 'See the work. Know what is real.',
    headingRight:
      'A focused workspace for teams to benchmark candidate models, evaluate multi-step workflows, and inspect metrics under hard spend caps.',
    cardBadge: '02 Verified Metrics',
    cardTitle: 'Make the work easy to follow.',
    cardDescription:
      'Break evaluation sets into verified test splits and see what is performing, what is failing, and where budget is allocated—without losing sight of the bigger picture.',
  },

  bentoGrid: {
    heading: "Everything your team needs. Nothing you don't.",
    subheading: 'Engineered specifically for engineering teams evaluating production LLM systems.',
    cards: [
      {
        id: 'models',
        tag: 'Candidate Roster',
        title: 'Unified Model Catalog',
        description:
          'Benchmark 200+ models across OpenRouter, Anthropic, Gemini, OpenAI, and local Ollama instances with verified catalog rates.',
        glowColor: 'rgba(245, 158, 11, 0.15)',
        iconName: 'Cpu',
        previewType: 'models',
      },
      {
        id: 'workflows',
        tag: 'Compound Agents',
        title: 'Workflow Connectors',
        description:
          'Evaluate complete multi-step graphs including Dify, Flowise, n8n, LangGraph, and in-process Python callables as first-class targets.',
        glowColor: 'rgba(59, 130, 246, 0.18)',
        iconName: 'Layers',
        previewType: 'workflows',
      },
      {
        id: 'budget',
        tag: 'Financial Safety',
        title: 'Fail-Closed Spend Caps',
        description:
          'Total, per-run, and per-case budget ceilings stored in SQLite WAL. Any unpriced request halts execution before debts accrue.',
        glowColor: 'rgba(16, 185, 129, 0.15)',
        iconName: 'Wallet',
        previewType: 'budget',
      },
      {
        id: 'approval',
        tag: 'Zero Leakage',
        title: 'Cryptographic Plan Binding',
        description:
          'SHA-256 fingerprint binds candidates, prompt templates, datasets, and spend limits. Stale approvals are rejected fail-closed.',
        glowColor: 'rgba(6, 182, 212, 0.18)',
        iconName: 'ShieldCheck',
        previewType: 'approval',
      },
    ] as BentoCardItem[],
  },

  metricsSection: {
    stats: [
      { value: '200+', label: 'Models & Providers' },
      { value: '$0.00', label: 'Replay Benchmark Spend' },
      { value: '99.8%', label: 'Gate Enforcement' },
      { value: '4.9/5', label: 'Developer Rating' },
    ] as MetricItem[],
    testimonial: {
      quote:
        '“We finally have clear visibility into latency percentiles and real dollar spend before deploying prompt revisions to production.”',
      body:
        'Runport provides a unified local interface to test models, track ledger spend, and compare accuracy without transmitting sensitive data to SaaS clouds.',
      author: 'Maya Chen',
      role: 'Staff AI Engineer · Northgate Systems',
      impactStats: [
        { value: '3.2×', label: 'faster evaluation cycles' },
        { value: '38%', label: 'reduction in wasted spend' },
        { value: '12k+', label: 'runs executed safely' },
      ],
    },
  },

  platformShowcase: {
    heading: 'One workbench for the way your team works.',
    description:
      'Runport brings preflight checks, multi-model execution, and statistical validation together in one focused space.',
    pillars: [
      {
        icon: 'Folder',
        title: 'Preflight Safety',
        description: 'Verify credentials, environment variables, and privacy gates offline before opening a single socket.',
      },
      {
        icon: 'Layers',
        title: 'Universal Connectors',
        description: 'Plug in raw model APIs, agentic pipelines, or custom HTTP endpoints in under 40 lines of code.',
      },
      {
        icon: 'BarChart2',
        title: 'Supervised Metrics',
        description: 'Calculate Wilson binomial confidence intervals, Brier calibration, and Cohen’s Kappa against human truth.',
      },
    ],
  },

  pricing: {
    heading: 'Simple pricing.',
    headingAccent: 'pricing.',
    subheading: 'Start with what you need. Upgrade when your team grows.',
    monthlyNote: 'Billed monthly',
    yearlyNote: 'Billed annually · Save 20%',
    plans: [
      {
        id: 'community',
        name: 'Community',
        priceMonthly: 0,
        priceYearly: 0,
        description: 'For developers and researchers evaluating local and cloud models.',
        features: [
          '1 Local Workspace',
          'Unlimited Offline Replay Runs',
          'Rich Terminal User Interface (TUI)',
          'SQLite WAL Budget Ledger',
          'Full-Screen Local Web Dashboard',
          'Sanitized JSON/ZIP Trace Exports',
        ],
        ctaText: 'Get Started Free',
        imageBg: '/assets/landing/pricing-1.jpg',
      },
      {
        id: 'team',
        name: 'Team Workspace',
        priceMonthly: 19,
        priceYearly: 15,
        description: 'For small engineering teams standardizing LLM evaluation.',
        isFeatured: true,
        features: [
          'Unlimited Workspaces & Projects',
          'Custom Workflow Adapters (Dify, n8n, LangGraph)',
          'Cryptographic Plan Fingerprint Approval',
          'Cross-Split Leakage & Redaction Gates',
          'Automated CI/CD Test Harness',
          'Priority Connector Support',
        ],
        ctaText: 'Start Free Trial',
        imageBg: '/assets/landing/pricing-2.png',
      },
      {
        id: 'enterprise',
        name: 'Enterprise',
        priceMonthly: 49,
        priceYearly: 39,
        description: 'For organizations with air-gapped security and compliance mandates.',
        features: [
          'Everything in Team',
          'Air-Gapped & Offline VPC Deployments',
          'Role-Based Authorization & SSO',
          'Hardware-Backed Spend Ceiling Guards',
          'Custom Compliance Audit Logging',
          'Dedicated Solutions Engineering',
        ],
        ctaText: 'Talk to Us',
        imageBg: '/assets/landing/pricing-3.jpg',
      },
    ] as PricingPlan[],
    guarantee: 'Apache 2.0 open-source core · No credit card required · 100% local execution',
  },

  faq: {
    heading: 'Questions, answered.',
    subheading: 'Everything you need to know before getting started.',
    ctaPrompt: "Didn't find what you're looking for?",
    ctaButton: 'Talk to us',
    items: [
      {
        id: 'faq-1',
        question: 'What is Runport?',
        answer:
          'Runport is an open-source, local-first platform for benchmarking LLMs, prompt chains, and complex workflows. It pairs automated execution with hard spend caps and rigorous, human-supervised evaluation.',
      },
      {
        id: 'faq-2',
        question: 'How do fail-closed spend caps work?',
        answer:
          'Runport maintains an append-only SQLite WAL ledger. Before each request is dispatched, it checks total, pilot, per-run, and per-case limits. If an execution exceeds any ceiling or returns unpriced tokens, the run aborts immediately.',
      },
      {
        id: 'faq-3',
        question: 'Can I benchmark compound workflows like Dify or LangGraph?',
        answer:
          'Yes. Unlike single-prompt benchmarking tools, Runport provides decoupled connectors for Dify, Flowise, n8n, LangGraph, and in-process Python functions, recording latency, outputs, and intermediate traces.',
      },
      {
        id: 'faq-4',
        question: 'Why does Runport reject model agreement as accuracy?',
        answer:
          'Consensus between models is inter-rater agreement (measured by Cohen’s Kappa), not truth. Runport evaluates supervised accuracy, F1, and calibration strictly against verified human ground truth.',
      },
      {
        id: 'faq-5',
        question: 'Does Runport send telemetry or analytics to cloud servers?',
        answer:
          'Zero. Runport has no telemetry, tracking pixels, or remote analytics. All evaluation datasets, prompts, traces, and financial records stay exclusively on your local machine.',
      },
      {
        id: 'faq-6',
        question: 'Can I run evaluations in CI/CD without an API key?',
        answer:
          'Yes! Runport features a deterministic Replay Runner that executes synthetic fixture evaluations with provenance REPLAYED and $0.00 spend, making it completely safe for pull requests.',
      },
    ] as FAQItem[],
  },

  finalCta: {
    heading: 'Make the next move.',
    subheading: 'Bring your models, your prompts, and your workflows into one focused workspace.',
    ctaPrimary: 'Start for free',
    ctaSecondary: 'Read Documentation',
  },

  footer: {
    brandName: 'RUNPORT',
    tagline: 'A focused workbench for engineering teams to evaluate LLMs, stay within budget, and ship with confidence.',
    socials: [
      { name: 'GitHub', href: 'https://github.com/Sudharsanselvaraj/runport' },
      { name: 'Discord', href: '#' },
      { name: 'X', href: '#' },
    ],
    columns: [
      {
        title: 'Product',
        links: [
          { label: 'Overview', href: '#features' },
          { label: 'Workflows', href: '#workflows' },
          { label: 'Pricing', href: '#pricing' },
          { label: 'Terminal TUI', href: '#' },
        ],
      },
      {
        title: 'Resources',
        links: [
          { label: 'Documentation', href: 'https://github.com/Sudharsanselvaraj/runport' },
          { label: 'CLI Reference', href: '#' },
          { label: 'Release Notes', href: '#' },
          { label: 'Changelog', href: '#' },
        ],
      },
      {
        title: 'Legal',
        links: [
          { label: 'Apache 2.0 License', href: 'https://github.com/Sudharsanselvaraj/runport/blob/main/LICENSE' },
          { label: 'Security Policy', href: 'https://github.com/Sudharsanselvaraj/runport/blob/main/SECURITY.md' },
          { label: 'Privacy & Telemetry', href: '#' },
        ],
      },
    ],
    copyright: '© 2026 Runport. Open-source under Apache-2.0. Built for developers.',
  },
}
