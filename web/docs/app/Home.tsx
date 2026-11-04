import React from 'react'
import { NAV, getPage } from './content'
import { pageHref } from './router'

interface CardSpec {
  slug: string
  title: string
  body: string
}

const SECTIONS: { title: string; cards: CardSpec[] }[] = [
  {
    title: 'Popular',
    cards: [
      { slug: 'quickstart', title: 'Quickstart', body: 'Validate a dataset, run the offline preflight and a $0.00 replay benchmark in a few minutes.' },
      { slug: 'provider-configuration', title: 'Connect providers', body: 'Point Runport at OpenRouter, an OpenAI-compatible server or a local Ollama model.' },
      { slug: 'creating-benchmarks', title: 'Create benchmarks', body: 'Wrap any model, workflow or Python callable as a target and run it through the guarded runner.' },
      { slug: 'scorers', title: 'Evaluate results', body: 'Score outputs with exact-match, classification, extraction and generation scorers.' },
    ],
  },
  {
    title: 'Core concepts',
    cards: [
      { slug: 'architecture', title: 'Architecture', body: 'Targets, the seven-stage runner guard, the SQLite WAL ledger and the three interfaces.' },
      { slug: 'runs-and-plans', title: 'Runs and plans', body: 'How an execution plan is fingerprinted, approved and turned into a stored run.' },
      { slug: 'datasets', title: 'Datasets', body: 'The JSONL case schema, confidentiality classes, splits and leakage checks.' },
      { slug: 'scorers', title: 'Scorers', body: 'The BaseScorer contract and every scorer that ships in runport.scorers.' },
      { slug: 'quality-metrics', title: 'Metrics', body: 'Accuracy, per-class F1, Wilson and bootstrap intervals, Brier score and kappa.' },
      { slug: 'reproducibility', title: 'Reproducibility', body: 'Plan fingerprints, dataset hashing, fixed seeds and deterministic replay.' },
    ],
  },
  {
    title: 'Developer guides',
    cards: [
      { slug: 'openai-compatible', title: 'Configure model providers', body: 'Benchmark any Chat Completions endpoint with the openai_compat connector.' },
      { slug: 'executing-runs', title: 'Run your first benchmark', body: 'Use runport benchmark in explain, replay and live modes under spend caps.' },
      { slug: 'custom-http', title: 'Evaluate AI workflows', body: 'Benchmark any workflow behind an HTTP endpoint with payload templates.' },
      { slug: 'understanding-results', title: 'Understand benchmark results', body: 'Read case statuses, cost provenance and the metrics a run reports.' },
    ],
  },
]

export const DocsHomeCard: React.FC<CardSpec> = ({ slug, title, body }) => {
  const group = getPage(slug)?.group ?? ''
  return (
    <a className="rd-card" href={pageHref(slug)}>
      <span className="rd-card-tag">{group}</span>
      <span className="rd-card-text">
        <span className="rd-card-title">{title}</span>
        <span className="rd-card-body">{body}</span>
      </span>
    </a>
  )
}

export const DocsHome: React.FC = () => (
  <div className="rd-home">
    <header className="rd-home-head">
      <h1>Runport Documentation</h1>
      <p className="rd-lede">Everything you need to benchmark, evaluate and compare language models and AI workflows.</p>
    </header>

    {SECTIONS.map((s) => (
      <section key={s.title} className="rd-home-section" aria-labelledby={`rd-${s.title}`}>
        <h2 id={`rd-${s.title}`}>{s.title}</h2>
        <div className="rd-card-grid">
          {s.cards.map((c) => (
            <DocsHomeCard key={`${s.title}-${c.slug}`} {...c} />
          ))}
        </div>
      </section>
    ))}

    <section className="rd-home-section" aria-labelledby="rd-all">
      <h2 id="rd-all">All sections</h2>
      <div className="rd-index">
        {NAV.map((g) => (
          <div key={g.title} className="rd-index-group">
            <h3>{g.title}</h3>
            <ul>
              {g.pages.map((slug) => (
                <li key={slug}>
                  <a href={pageHref(slug)}>{getPage(slug)?.title}</a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  </div>
)
