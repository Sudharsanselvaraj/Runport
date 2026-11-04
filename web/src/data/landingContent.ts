// Landing page copy. Layout lives in components/landing; edit words here.
// Every number and claim below must be verifiable in this repository.

export interface NavItem {
  label: string
  href: string
  isExternal?: boolean
}

export type MockupKind = 'plan' | 'run' | 'score' | 'ledger' | 'models' | 'datasets' | 'connectors' | 'traces' | 'compare'

export interface ShowcaseStep {
  tag: string
  title: string
  body: string
  mockup: MockupKind
}

export interface CarouselCard {
  icon: 'cpu' | 'database' | 'workflow' | 'wallet' | 'activity' | 'git-compare'
  title: string
  body: string
  mockup: MockupKind
  tint: 'olive' | 'teal'
}

export interface Stat {
  value: number
  prefix?: string
  suffix?: string
  decimals?: number
  label: string
}

export type FeatureIcon = 'terminal' | 'monitor' | 'folder' | 'file' | 'shield' | 'git'

export interface PricingPlan {
  id: string
  tag: string
  price: string
  unit: string
  description: string
  features: { icon: FeatureIcon; label: string }[]
  image: string
}

export interface WayItem {
  kind: 'cli' | 'tui' | 'web'
  title: string
  body: string
  image: string
  action: { type: 'copy'; text: string } | { type: 'link'; label: string; href: string }
}

export interface PillarTab {
  key: 'spend' | 'truth' | 'local'
  label: string
  eyebrow: string
  title: string
  body: string
  rows: { icon: 'gauge' | 'fingerprint' | 'ledger' | 'interval' | 'agree' | 'null' | 'shield' | 'eraser' | 'replay'; title: string; body: string }[]
}

export interface RunTarget {
  key: 'local' | 'docker' | 'ci'
  title: string
  body: string
  link: { label: string; href: string }
}

export interface FAQItem {
  id: string
  question: string
  answer: string
}

const REPO = 'https://github.com/Sudharsanselvaraj/runport'

export const LANDING_CONTENT = {
  repo: REPO,

  navigation: {
    brandName: 'RUNPORT',
    links: [
      { label: 'Product', href: '#product' },
      { label: 'Features', href: '#features' },
      { label: 'Install', href: '#ways' },
      { label: 'Docs', href: `${REPO}#readme`, isExternal: true },
    ] as NavItem[],
    ctaSecondary: 'GitHub',
    ctaPrimary: 'Get started',
    ctaPrimaryHref: `${REPO}#quickstart`,
  },

  hero: {
    title: 'Benchmark what’s real.',
    description: 'A local-first workbench for models, prompts, and agent workflows, under hard spend caps.',
    ctaPrimary: 'Get started',
    ctaPrimaryHref: `${REPO}#quickstart`,
    ctaSecondary: 'See how it works',
    marqueeLabel: 'Benchmarks targets across.',
    // Connectors and providers that ship in src/runport/connectors and providers/.
    marquee: ['OpenRouter', 'Ollama', 'Dify', 'Flowise', 'Langflow', 'n8n', 'LangGraph', 'OpenAI-compatible', 'HTTP workflows', 'Python callables'],
  },

  statement: {
    lead: 'Evals shouldn’t run',
    tail: 'on guesswork.',
  },

  // Scroll-driven flow: targets -> Runport guards -> run trace -> scorecard.
  // Target names are the connectors in src/runport/connectors (logos in
  // web/landing/public/assets/landing/logos, used to identify the integrations); the trace and
  // scores are illustrative and labelled "Sample run" on the page.
  stackFlow: {
    titleA: 'Keep your stack.',
    titleB: 'Runport benchmarks it.',
    description: 'Model APIs, local models, workflow engines and plain Python. Every target runs through the same seven guards into one trace and one scorecard.',
    cta: 'See all connectors',
    ctaHref: `${REPO}#integrations`,
    groups: [
      {
        label: 'Model APIs',
        cols: 2,
        tiles: [
          { name: 'OpenRouter', logo: '/assets/landing/logos/openrouter.svg' },
          { name: 'OpenAI-compatible', logo: '/assets/landing/logos/openai.svg' },
          { name: 'Ollama', logo: '/assets/landing/logos/ollama.svg' },
          { name: 'vLLM', logo: '/assets/landing/logos/vllm.svg' },
        ],
      },
      {
        label: 'Workflows',
        cols: 3,
        tiles: [
          { name: 'Dify', logo: '/assets/landing/logos/dify.svg' },
          { name: 'Flowise', logo: '/assets/landing/logos/flowise.png', exp: true },
          { name: 'Langflow', logo: '/assets/landing/logos/langflow.svg', exp: true },
          { name: 'n8n', logo: '/assets/landing/logos/n8n.svg', exp: true },
          { name: 'LangGraph', logo: '/assets/landing/logos/langgraph.svg', exp: true },
          { name: 'HTTP endpoint', icon: 'globe' },
        ],
      },
      {
        label: 'Code',
        cols: 2,
        tiles: [
          { name: 'Python callable', logo: '/assets/landing/logos/python.svg' },
          { name: 'Subprocess', icon: 'terminal' },
          { name: 'Plugins', icon: 'puzzle' },
          { name: 'Replay', icon: 'replay' },
        ],
      },
    ] as { label: string; cols: number; tiles: { name: string; logo?: string; icon?: 'globe' | 'terminal' | 'puzzle' | 'replay'; exp?: boolean }[] }[],
    guards: ['Authorize', 'Privacy gate', 'Preflight', 'Transport', 'Validate', 'Persist', 'Book spend'],
    trace: {
      title: 'Sample run',
      meta: 'plan 3f9a2c1e · 5 of 50 cases',
      total: '4.96s',
      rows: [
        { id: 'case-001', status: 'OK', ms: 1120, basis: 'ESTIMATED' },
        { id: 'case-002', status: 'OK', ms: 840, basis: 'ESTIMATED' },
        { id: 'case-003', status: 'INVALID_OUTPUT', ms: 1620, basis: 'ESTIMATED', flag: true },
        { id: 'case-004', status: 'OK', ms: 410, basis: 'ESTIMATED' },
        { id: 'case-005', status: 'OK', ms: 970, basis: 'ESTIMATED' },
      ] as { id: string; status: string; ms: number; basis: string; flag?: boolean }[],
    },
    scores: [
      { label: 'Accuracy', value: 0.84, decimals: 2, note: 'Wilson 95% 0.71–0.92' },
      { label: 'p95 latency', value: 1.62, decimals: 2, suffix: 's', note: 'n = 50' },
      { label: 'Cost / 1k cases', value: 0.82, decimals: 2, prefix: '$', note: 'ESTIMATED' },
      { label: 'Invalid rate', value: 0.04, decimals: 2, note: '2 of 50 · in denominator', flag: true },
      { label: 'Agreement κ', value: 0.61, decimals: 2, note: 'not accuracy' },
      { label: 'Unresolved', value: 0, decimals: 0, prefix: '$', note: 'live runs unblocked' },
    ] as { label: string; value: number; decimals: number; prefix?: string; suffix?: string; note: string; flag?: boolean }[],
  },

  showcase: {
    titleA: 'See every run.',
    titleB: 'Know what’s real.',
    aside: 'Plan a benchmark, run it under a fail-closed budget, score it against human truth, and reconcile every cent.',
    steps: [
      {
        tag: '01  Plan',
        title: 'Approve exactly what will run.',
        body: 'Pick candidates, a dataset and a prompt template. Runport hashes them with your budget caps into one SHA-256 plan fingerprint, and rejects any approval that no longer matches.',
        mockup: 'plan',
      },
      {
        tag: '02  Run',
        title: 'Watch it execute, case by case.',
        body: 'Every request passes the same guard order: authorization, privacy gate, preflight budget check, transport, validation, persistence, spend booking. Nothing skips a step.',
        mockup: 'run',
      },
      {
        tag: '03  Score',
        title: 'Score against human truth.',
        body: 'Accuracy, F1 and calibration come only from approved annotations, with Wilson intervals. Model-to-model agreement is reported as agreement, never as correctness.',
        mockup: 'score',
      },
      {
        tag: '04  Reconcile',
        title: 'Know where every cent went.',
        body: 'Spend lands in an append-only SQLite WAL ledger as ACTUAL, ESTIMATED, UNRESOLVED or UNAVAILABLE. Unresolved spend blocks the next live run until you reconcile it.',
        mockup: 'ledger',
      },
    ] as ShowcaseStep[],
  },

  carousel: {
    titleA: 'Everything a benchmark needs.',
    titleB: 'Nothing it doesn’t.',
    cards: [
      { icon: 'cpu', title: 'Models', body: 'Compare providers and local models side by side with catalog rates you can verify.', mockup: 'models', tint: 'olive' },
      { icon: 'workflow', title: 'Workflows', body: 'Benchmark Dify, Flowise, n8n, LangGraph or any HTTP endpoint as a first-class target.', mockup: 'connectors', tint: 'teal' },
      { icon: 'database', title: 'Datasets', body: 'Validate schemas, catch split leakage, and hash sources before and after every run.', mockup: 'datasets', tint: 'olive' },
      { icon: 'wallet', title: 'Budgets', body: 'Total, per-run and per-case ceilings that halt execution before a request can overspend.', mockup: 'ledger', tint: 'olive' },
      { icon: 'activity', title: 'Traces', body: 'Inspect every request and response with secrets scrubbed, then export sanitized ZIPs.', mockup: 'traces', tint: 'teal' },
      { icon: 'git-compare', title: 'Compare', body: 'Put two runs next to each other: accuracy, latency percentiles, tokens and cost.', mockup: 'compare', tint: 'teal' },
    ] as CarouselCard[],
  },

  metrics: {
    stats: [
      { value: 9, label: 'Target connectors' },
      { value: 7, label: 'Guard stages per request' },
      { value: 0, prefix: '$', decimals: 2, label: 'Spend on replay runs' },
      { value: 0, label: 'Telemetry calls' },
    ] as Stat[],
    proof: {
      quote: '“Null is not 0.”',
      body: 'Missing tokens, latency, confidence or cost stay UNAVAILABLE. Runport never fills a gap with a zero, so a cheap-looking row is never a missing one.',
      source: 'Architectural invariant #1',
      sourceDetail: 'AGENTS.md · enforced by tests',
      facts: [
        { value: 'SHA-256', label: 'plan fingerprint' },
        { value: '4', label: 'cost provenance states' },
        { value: '100%', label: 'local, offline-testable' },
      ],
    },
  },

  platform: {
    title: 'One workbench for every way you evaluate.',
    description: 'Runport brings preflight checks, execution and statistics together in one local space.',
    pillars: [
      { title: 'Preflight', body: 'Verify keys, budgets and privacy gates offline before a socket opens.' },
      { title: 'Execution', body: 'Run models, prompts and workflows under one guard order.' },
      { title: 'Evidence', body: 'Wilson intervals, Brier calibration and Cohen’s kappa on human truth.' },
    ],
  },

  pricing: {
    titleA: 'Simple',
    titleB: 'pricing.',
    subheading: 'Runport is open source. You only pay your providers, and only up to your caps.',
    toggle: ['Replay', 'Live'] as const,
    spendNote: {
      Replay: 'REPLAYED provenance · $0.00 provider spend',
      Live: 'Provider spend booked to your capped ledger',
    },
    plans: [
      {
        id: 'local',
        tag: 'Terminal',
        price: '$0',
        unit: '/ forever',
        description: 'The CLI and Rich terminal UI on your own machine.',
        features: [
          { icon: 'terminal', label: 'Full CLI & terminal UI' },
          { icon: 'folder', label: 'Local SQLite WAL ledger' },
          { icon: 'file', label: 'Dataset validation' },
          { icon: 'shield', label: 'Secret scrubbing' },
        ],
        image: '/assets/landing/pricing-1.jpg',
      },
      {
        id: 'workbench',
        tag: 'Workbench',
        price: '$0',
        unit: '/ forever',
        description: 'Everything in Terminal, plus the local web dashboard.',
        features: [
          { icon: 'monitor', label: 'Web dashboard on 127.0.0.1' },
          { icon: 'git', label: 'Run comparison & reports' },
          { icon: 'folder', label: 'Workflow connectors' },
          { icon: 'file', label: 'Sanitized trace exports' },
          { icon: 'shield', label: 'Plan fingerprint approval' },
          { icon: 'monitor', label: 'Live budget status' },
        ],
        image: '/assets/landing/pricing-2.png',
      },
      {
        id: 'ci',
        tag: 'CI',
        price: '$0',
        unit: '/ forever',
        description: 'Deterministic replay runs inside your pull requests.',
        features: [
          { icon: 'git', label: 'Replay runner, no API key' },
          { icon: 'shield', label: 'Offline test suite' },
          { icon: 'file', label: 'Invariant tests' },
          { icon: 'terminal', label: 'Exit codes for gating' },
          { icon: 'folder', label: 'Import / export traces' },
        ],
        image: '/assets/landing/pricing-3.jpg',
      },
    ] as PricingPlan[],
    footnote: 'Apache-2.0 · No account · No telemetry.',
  },

  // "Three ways to run": the three local interfaces. Window contents mirror real
  // command output (validate-dataset on the bundled seed dataset, default ceilings).
  waysToRun: {
    titleA: 'Benchmark',
    titleB: 'your way.',
    subheading: 'Three ways to run Runport, with the same guards in every one.',
    items: [
      {
        kind: 'cli',
        title: 'Command line',
        body: 'Validate datasets, run benchmarks and reconcile spend straight from your terminal.',
        image: '/assets/landing/pricing-1.jpg',
        action: { type: 'copy', text: 'uv run runport' },
      },
      {
        kind: 'tui',
        title: 'Terminal UI',
        body: 'A full-screen dashboard for spend, ceilings, model readiness and error rates.',
        image: '/assets/landing/pricing-2.png',
        action: { type: 'link', label: 'Read the quickstart', href: `${REPO}#quickstart` },
      },
      {
        kind: 'web',
        title: 'Web dashboard',
        body: 'A local FastAPI and React dashboard on 127.0.0.1. Nothing leaves your machine.',
        image: '/assets/landing/pricing-3.jpg',
        action: { type: 'link', label: 'View on GitHub', href: REPO },
      },
    ] as WayItem[],
  },

  // Tabbed pillars (spend, truth, local). Every row maps to shipped behaviour;
  // mockup numbers are illustrative and labelled "Sample" on the page.
  pillars: {
    titleA: 'Benchmarks you',
    titleB: 'can trust.',
    subheading: 'From the first request to the final number, Runport keeps spend, scores and data honest.',
    tabs: [
      {
        key: 'spend',
        label: 'Spend',
        eyebrow: 'Fail-closed spend',
        title: 'Every request checked before it’s sent.',
        body: 'Ceilings are checked before each live request. A billed request with unknown cost is booked UNRESOLVED and blocks the next live run until you reconcile it.',
        rows: [
          { icon: 'gauge', title: 'Hard ceilings', body: 'Total, pilot, per-run and per-case limits from runport.yaml.' },
          { icon: 'fingerprint', title: 'Plan-bound approval', body: 'A typed confirmation tied to the plan’s SHA-256 fingerprint.' },
          { icon: 'ledger', title: 'Append-only ledger', body: 'Every cost labelled ACTUAL, ESTIMATED, UNRESOLVED or UNAVAILABLE.' },
        ],
      },
      {
        key: 'truth',
        label: 'Truth',
        eyebrow: 'Defensible scores',
        title: 'Scored against human truth, or not at all.',
        body: 'Accuracy and F1 come only from human-approved labels, with confidence intervals. What wasn’t measured stays empty, never zero.',
        rows: [
          { icon: 'interval', title: 'Wilson intervals', body: '95% intervals on proportions, bootstrap for latency and cost.' },
          { icon: 'agree', title: 'Agreement isn’t accuracy', body: 'Model-to-model agreement is reported as kappa, never as correctness.' },
          { icon: 'null', title: 'Null is not 0', body: 'Unlabelled cases stay unscored and are left out of every mean.' },
        ],
      },
      {
        key: 'local',
        label: 'Local',
        eyebrow: 'Local by default',
        title: 'Nothing leaves your machine.',
        body: 'No account and no telemetry. Datasets, traces and the ledger live in SQLite on your disk, and secrets are scrubbed before anything is written.',
        rows: [
          { icon: 'shield', title: 'Privacy gate', body: 'A forbidden field aborts the whole batch before a socket opens.' },
          { icon: 'eraser', title: 'Secret scrubbing', body: 'Keys and bearer tokens removed from logs, traces and exports.' },
          { icon: 'replay', title: 'Offline replay', body: 'Score recorded runs in CI with no key and $0.00 spend.' },
        ],
      },
    ] as PillarTab[],
  },

  runAnywhere: {
    titleLead: 'Run it',
    titleKey: 'anywhere',
    titleTail: 'you work',
    product: 'Open source · Apache-2.0',
    targets: [
      {
        key: 'local',
        title: 'Local',
        body: 'Clone, sync and run on your laptop. Python 3.11 or newer.',
        link: { label: 'Read the quickstart', href: `${REPO}#quickstart` },
      },
      {
        key: 'docker',
        title: 'Docker',
        body: 'Build the image from the repository’s Dockerfile and serve the dashboard from a container.',
        link: { label: 'View the Dockerfile', href: `${REPO}/blob/main/Dockerfile` },
      },
      {
        key: 'ci',
        title: 'CI',
        body: 'Replay recorded runs on every pull request: offline, no key, $0.00.',
        link: { label: 'See our CI workflow', href: `${REPO}/blob/main/.github/workflows/ci.yml` },
      },
    ] as RunTarget[],
    callout: {
      title: 'No cloud required.',
      body: 'There is no hosted Runport and no account. Your data, traces and ledger stay on your machine.',
      checks: ['No account', 'No telemetry', 'Apache-2.0'],
      cta: 'Star on GitHub',
      href: REPO,
    },
  },

  faq: {
    titleA: 'Questions,',
    titleB: 'answered.',
    subheading: 'Everything you need to know before your first run.',
    ctaPrompt: 'Didn’t find what you’re looking for?',
    ctaButton: 'Open an issue',
    ctaHref: `${REPO}/issues`,
    items: [
      {
        id: 'what',
        question: 'What is Runport?',
        answer: 'An open-source, local-first platform for benchmarking LLMs, prompt templates and orchestrated workflows, with hard spend caps and supervised metrics computed only from human-approved ground truth.',
      },
      {
        id: 'caps',
        question: 'How do fail-closed spend caps work?',
        answer: 'Before a request is sent, Runport checks it against total, per-run and per-case ceilings in an append-only SQLite WAL ledger. If a request cannot be priced it is booked as UNRESOLVED, and further live runs stay blocked until you run runport budget reconcile.',
      },
      {
        id: 'workflows',
        question: 'Can I benchmark Dify, n8n or LangGraph workflows?',
        answer: 'Yes. Connectors for Dify, Flowise, Langflow, n8n, LangGraph, OpenAI-compatible APIs, Ollama, generic HTTP workflows and in-process Python callables all produce the same target result shape.',
      },
      {
        id: 'agreement',
        question: 'Why isn’t model agreement treated as accuracy?',
        answer: 'Agreement between models measures consensus, not truth. Runport reports it as agreement (for example Cohen’s kappa) and computes accuracy, F1 and calibration only against human-approved annotations.',
      },
      {
        id: 'telemetry',
        question: 'Does Runport send telemetry anywhere?',
        answer: 'No. Datasets, prompts, traces and the spend ledger stay on your machine, and the test suite runs fully offline against fake transports.',
      },
      {
        id: 'ci',
        question: 'Can I run it in CI without an API key?',
        answer: 'Yes. Replay runs execute recorded results with provenance REPLAYED and book $0.00, so they are safe to run on every pull request.',
      },
    ] as FAQItem[],
  },

  finalCta: {
    titleA: 'Run the next',
    titleB: 'benchmark.',
    subheading: 'Bring your models, prompts and workflows into one focused, local workbench.',
    cta: 'Star on GitHub',
    ctaHref: REPO,
  },

  footer: {
    brandName: 'RUNPORT',
    tagline: 'A local-first workbench to benchmark models and workflows under hard spend caps.',
    closing: 'Made for teams who measure before they ship.',
    columns: [
      {
        title: 'Product',
        icon: 'monitor' as FeatureIcon,
        links: [
          { label: 'Features', href: '#features' },
          { label: 'Install', href: '#ways' },
        ],
      },
      {
        title: 'Resources',
        icon: 'folder' as FeatureIcon,
        links: [
          { label: 'Docs', href: `${REPO}#readme` },
          { label: 'Issues', href: `${REPO}/issues` },
        ],
      },
      {
        title: 'Legal',
        icon: 'file' as FeatureIcon,
        links: [
          { label: 'License', href: `${REPO}/blob/main/LICENSE` },
          { label: 'Security', href: `${REPO}/blob/main/SECURITY.md` },
        ],
      },
    ],
    copyright: '© 2026 Runport. Apache-2.0.',
  },
}
