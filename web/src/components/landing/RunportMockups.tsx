// Product mockups built from the real Workbench's navigation and vocabulary.
// All figures are illustrative sample data and are labelled as such in the UI.
// Canvas: 680 × 700 (scaled by ScaledCanvas where needed).
import React from 'react'
import {
  Sliders, Cpu, Layers, Database, FileText, Play, CheckCircle2, GitCompare, BarChart2, Wallet, Search,
  ShieldCheck, Lock, AlertTriangle, Circle, type LucideIcon,
} from 'lucide-react'
import type { MockupKind } from '../../data/landingContent'

const NAV: { key: string; label: string; Icon: LucideIcon }[] = [
  { key: 'setup', label: 'Setup', Icon: Sliders },
  { key: 'models', label: 'Models', Icon: Cpu },
  { key: 'targets', label: 'Targets', Icon: Layers },
  { key: 'datasets', label: 'Datasets', Icon: Database },
  { key: 'plan', label: 'Plan', Icon: FileText },
  { key: 'run', label: 'Live Run', Icon: Play },
  { key: 'results', label: 'Results', Icon: CheckCircle2 },
  { key: 'compare', label: 'Compare', Icon: GitCompare },
  { key: 'reports', label: 'Reports', Icon: BarChart2 },
  { key: 'budget', label: 'Budget', Icon: Wallet },
]

const ACTIVE: Record<MockupKind, string> = {
  plan: 'plan', run: 'run', score: 'results', ledger: 'budget', models: 'models',
  datasets: 'datasets', connectors: 'targets', traces: 'reports', compare: 'compare',
}

const Prov: React.FC<{ p: 'ACTUAL' | 'ESTIMATED' | 'UNRESOLVED' | 'UNAVAILABLE' | 'REPLAYED' }> = ({ p }) => (
  <span className={`mk-prov mk-prov-${p.toLowerCase()}`}>{p}</span>
)

const Shell: React.FC<{ kind: MockupKind; children: React.ReactNode }> = ({ kind, children }) => (
  <div className="mk-app">
    <aside className="mk-side">
      <div className="mk-brand">
        <img src="/assets/landing/runport-emblem.png" alt="" width={18} height={18} />
        <span>RUNPORT</span>
      </div>
      <nav className="mk-nav">
        {NAV.map(({ key, label, Icon }) => (
          <div key={key} className={`mk-nav-item${ACTIVE[kind] === key ? ' is-active' : ''}`}>
            <Icon size={15} />
            <span>{label}</span>
          </div>
        ))}
      </nav>
      <div className="mk-side-foot">
        <div className="mk-wal"><span className="mk-dot mk-dot-green" />Local WAL active</div>
        <div className="mk-muted">127.0.0.1:8000</div>
      </div>
    </aside>
    <main className="mk-main">
      <div className="mk-top">
        <div className="mk-search"><Search size={14} /><span>Search runs, models, datasets…</span><kbd>⌘K</kbd></div>
        <span className="mk-sample">Sample data</span>
      </div>
      <div className="mk-body">{children}</div>
    </main>
  </div>
)

const Head: React.FC<{ crumb: string; title: string; badge?: React.ReactNode; sub?: string }> = ({ crumb, title, badge, sub }) => (
  <div className="mk-head">
    <div className="mk-crumb">{crumb}</div>
    <div className="mk-title-row"><h4>{title}</h4>{badge}</div>
    {sub && <p className="mk-sub">{sub}</p>}
  </div>
)

const Bar: React.FC<{ pct: number; tone?: 'green' | 'blue' | 'amber' }> = ({ pct, tone = 'green' }) => (
  <div className="mk-bar"><div className={`mk-bar-fill mk-tone-${tone}`} style={{ width: `${pct}%` }} /></div>
)

function Plan() {
  return (
    <>
      <Head crumb="Plans › ticket-intent" title="Ticket intent · v3" badge={<span className="mk-badge mk-badge-green"><ShieldCheck size={12} />Approved</span>} sub="TEST split · 240 cases · prompt template intent_v3.txt" />
      <div className="mk-card">
        <div className="mk-card-title">Candidates</div>
        <table className="mk-table">
          <thead><tr><th>Target</th><th>Route</th><th className="r">In / 1M</th><th className="r">Out / 1M</th></tr></thead>
          <tbody>
            <tr><td>gpt-4o-mini</td><td className="mk-mono">openrouter</td><td className="r">$0.15</td><td className="r">$0.60</td></tr>
            <tr><td>claude-3-5-haiku</td><td className="mk-mono">openrouter</td><td className="r">$0.80</td><td className="r">$4.00</td></tr>
            <tr><td>llama3.1:8b</td><td className="mk-mono">ollama · local</td><td className="r mk-null">—</td><td className="r mk-null">—</td></tr>
            <tr><td>support-triage flow</td><td className="mk-mono">dify · workflow</td><td className="r mk-null">—</td><td className="r mk-null">—</td></tr>
          </tbody>
        </table>
      </div>
      <div className="mk-grid-3">
        <div className="mk-stat"><span>Total cap</span><b>$5.00</b></div>
        <div className="mk-stat"><span>Per run</span><b>$2.00</b></div>
        <div className="mk-stat"><span>Per case</span><b>$0.02</b></div>
      </div>
      <div className="mk-card mk-fp">
        <Lock size={14} />
        <div>
          <div className="mk-card-title">Plan fingerprint</div>
          <div className="mk-mono mk-hash">sha256:9f2c41d0…7be3e41a</div>
        </div>
        <span className="mk-badge">binds models · routes · dataset · template · caps</span>
      </div>
    </>
  )
}

function Run() {
  const guards = ['Authorization', 'Privacy gate', 'Preflight', 'Transport', 'Validation', 'Persistence', 'Spend booking']
  const rows: [string, string, string, string, string, React.ComponentProps<typeof Prov>['p']][] = [
    ['case-132', 'gpt-4o-mini', '412 ms', '318', '$0.0001', 'ESTIMATED'],
    ['case-131', 'claude-3-5-haiku', '688 ms', '301', '$0.0004', 'ACTUAL'],
    ['case-131', 'llama3.1:8b', '1.21 s', '—', '—', 'UNAVAILABLE'],
    ['case-130', 'support-triage', '2.04 s', '—', '—', 'UNRESOLVED'],
    ['case-130', 'gpt-4o-mini', '397 ms', '322', '$0.0001', 'ESTIMATED'],
  ]
  return (
    <>
      <Head crumb="Live Run › ticket-intent v3" title="Running · 132 / 240" badge={<span className="mk-badge mk-badge-blue"><Circle size={8} fill="currentColor" />Live</span>} />
      <div className="mk-card">
        <div className="mk-row-between"><span className="mk-card-title">Progress · TEST split</span><span className="mk-num">55%</span></div>
        <Bar pct={55} tone="blue" />
      </div>
      <div className="mk-card">
        <div className="mk-card-title">Guard order</div>
        <div className="mk-guards">
          {guards.map((g, i) => (
            <span key={g} className={`mk-guard${i < 6 ? ' is-done' : ' is-active'}`}>{i < 6 ? <CheckCircle2 size={11} /> : <Circle size={9} />}{g}</span>
          ))}
        </div>
      </div>
      <div className="mk-card">
        <div className="mk-card-title">Events</div>
        <table className="mk-table">
          <thead><tr><th>Case</th><th>Target</th><th className="r">Latency</th><th className="r">Tokens</th><th className="r">Cost</th><th>Provenance</th></tr></thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}><td className="mk-mono">{r[0]}</td><td>{r[1]}</td><td className="r">{r[2]}</td><td className={`r${r[3] === '—' ? ' mk-null' : ''}`}>{r[3]}</td><td className={`r${r[4] === '—' ? ' mk-null' : ''}`}>{r[4]}</td><td><Prov p={r[5]} /></td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  )
}

function Score() {
  const classes: [string, number][] = [['billing', 94], ['tech_support', 92], ['account', 89], ['shipping', 90], ['other', 81]]
  return (
    <>
      <Head crumb="Results › ticket-intent v3 › gpt-4o-mini" title="Supervised metrics" badge={<span className="mk-badge mk-badge-green">Human-approved labels</span>} />
      <div className="mk-grid-3">
        <div className="mk-stat"><span>Accuracy</span><b>91.3%</b><em>Wilson 95% [87.0, 94.2]</em></div>
        <div className="mk-stat"><span>Macro F1</span><b>0.897</b><em>5 classes</em></div>
        <div className="mk-stat"><span>Brier</span><b>0.071</b><em>calibration</em></div>
      </div>
      <div className="mk-card">
        <div className="mk-card-title">Per-class accuracy</div>
        <div className="mk-bars">
          {classes.map(([c, v]) => (
            <div key={c} className="mk-bar-row"><span>{c}</span><Bar pct={v} /><b>{v}%</b></div>
          ))}
        </div>
      </div>
      <div className="mk-card mk-note">
        <AlertTriangle size={14} />
        <div><b>Agreement is not correctness.</b> κ = 0.81 between gpt-4o-mini and claude-3-5-haiku is reported as agreement only.</div>
      </div>
      <div className="mk-row-between mk-foot"><span>219 / 240 correct · TEST split · thresholds frozen on DEV</span><span className="mk-mono">run 2026-11-04</span></div>
    </>
  )
}

function Ledger() {
  const rows: [string, string, string, React.ComponentProps<typeof Prov>['p']][] = [
    ['run-0412', 'gpt-4o-mini', '$0.031', 'ESTIMATED'],
    ['run-0412', 'claude-3-5-haiku', '$0.118', 'ACTUAL'],
    ['run-0412', 'llama3.1:8b', '$0.00', 'UNAVAILABLE'],
    ['run-0412', 'support-triage', 'unknown', 'UNRESOLVED'],
    ['run-0409', 'replay fixture', '$0.00', 'REPLAYED'],
  ]
  return (
    <>
      <Head crumb="Budget › ledger" title="Spend ledger" badge={<span className="mk-badge mk-badge-green"><span className="mk-dot mk-dot-green" />WAL active</span>} />
      <div className="mk-card">
        <div className="mk-row-between"><span className="mk-card-title">Total cap · $5.00</span><span className="mk-num">$1.84 spent</span></div>
        <Bar pct={37} />
        <div className="mk-row-between mk-muted-row"><span>Per run $2.00</span><span>Per case $0.02</span><span>$3.16 remaining</span></div>
      </div>
      <div className="mk-card">
        <div className="mk-card-title">Entries (append-only)</div>
        <table className="mk-table">
          <thead><tr><th>Run</th><th>Target</th><th className="r">Amount</th><th>Provenance</th></tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i}><td className="mk-mono">{r[0]}</td><td>{r[1]}</td><td className={`r${r[2] === 'unknown' ? ' mk-null' : ''}`}>{r[2]}</td><td><Prov p={r[3]} /></td></tr>)}</tbody>
        </table>
      </div>
      <div className="mk-card mk-warn">
        <AlertTriangle size={14} />
        <div><b>1 unresolved entry blocks live runs.</b><div className="mk-mono mk-cmd">$ runport budget reconcile</div></div>
      </div>
    </>
  )
}

function Models() {
  const rows: [string, string, string, string, string][] = [
    ['gpt-4o-mini', 'OpenRouter', '128k', '$0.15', '$0.60'],
    ['claude-3-5-haiku', 'OpenRouter', '200k', '$0.80', '$4.00'],
    ['gemini-1.5-flash', 'OpenRouter', '1M', '$0.08', '$0.30'],
    ['llama3.1:8b', 'Ollama', '128k', '—', '—'],
    ['qwen2.5:7b', 'Ollama', '32k', '—', '—'],
  ]
  return (
    <>
      <Head crumb="Models › roster" title="Model roster" sub="Rates from the verified catalog; local models stay unpriced." />
      <div className="mk-card">
        <table className="mk-table">
          <thead><tr><th>Model</th><th>Provider</th><th className="r">Context</th><th className="r">In / 1M</th><th className="r">Out / 1M</th><th>Status</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r[0]}><td>{r[0]}</td><td>{r[1]}</td><td className="r">{r[2]}</td><td className={`r${r[3] === '—' ? ' mk-null' : ''}`}>{r[3]}</td><td className={`r${r[4] === '—' ? ' mk-null' : ''}`}>{r[4]}</td><td>{r[3] === '—' ? <Prov p="UNAVAILABLE" /> : <span className="mk-badge mk-badge-green">Verified</span>}</td></tr>)}</tbody>
        </table>
      </div>
    </>
  )
}

function Datasets() {
  const checks = ['Schema: required fields present', 'No forbidden fields', 'No DEV/TEST leakage', 'Secrets redacted', 'SHA-256 unchanged after run']
  return (
    <>
      <Head crumb="Datasets › ticket_intent.jsonl" title="ticket_intent.jsonl" badge={<span className="mk-badge mk-badge-green">Valid</span>} sub="240 TEST · 120 DEV · 5 labels" />
      <div className="mk-card">
        <div className="mk-card-title">Validation</div>
        <div className="mk-checks">{checks.map((c) => <div key={c}><CheckCircle2 size={13} className="mk-ok" />{c}</div>)}</div>
      </div>
      <div className="mk-card mk-fp">
        <Lock size={14} />
        <div><div className="mk-card-title">Source hash</div><div className="mk-mono mk-hash">sha256:c07a5e19…02df8b6c</div></div>
      </div>
    </>
  )
}

function Connectors() {
  const rows: [string, string, string][] = [
    ['Dify workflow', 'POST /v1/workflows/run', 'dify'],
    ['n8n webhook', 'POST /webhook/triage', 'n8n'],
    ['LangGraph agent', 'in-process graph', 'langgraph'],
    ['Flowise chatflow', 'POST /api/v1/prediction', 'flowise'],
    ['Custom endpoint', 'POST /v1/chat', 'http_workflow'],
  ]
  return (
    <>
      <Head crumb="Targets" title="Workflow targets" sub="Every connector returns the same TargetResult shape." />
      <div className="mk-list">
        {rows.map((r) => (
          <div key={r[0]} className="mk-list-item">
            <span className="mk-dot mk-dot-blue" />
            <div><b>{r[0]}</b><div className="mk-mono mk-muted">{r[1]}</div></div>
            <span className="mk-badge">{r[2]}</span>
          </div>
        ))}
      </div>
    </>
  )
}

function Traces() {
  return (
    <>
      <Head crumb="Reports › traces › case-131" title="Trace · case-131" badge={<span className="mk-badge mk-badge-green">Scrubbed</span>} />
      <div className="mk-card mk-code">
        <div><span className="k">POST</span> /api/v1/chat/completions</div>
        <div><span className="k">authorization</span>: <span className="s">Bearer [REDACTED]</span></div>
        <div><span className="k">model</span>: <span className="s">"claude-3-5-haiku"</span></div>
        <div><span className="k">latency_ms</span>: 688</div>
        <div><span className="k">usage</span>: {'{'} prompt: 214, completion: 87 {'}'}</div>
        <div><span className="k">cost_usd</span>: 0.0004 <span className="c">// ACTUAL</span></div>
      </div>
      <div className="mk-row-between mk-foot"><span>export-traces -f zip</span><span className="mk-mono">secrets: 0 found</span></div>
    </>
  )
}

function Compare() {
  const rows: [string, string, string][] = [['Accuracy', '91.3%', '88.8%'], ['p50 latency', '402 ms', '671 ms'], ['p90 latency', '610 ms', '1.02 s'], ['Cost / 1k cases', '$0.13', '$0.49']]
  return (
    <>
      <Head crumb="Compare › run-0412" title="gpt-4o-mini vs claude-3-5-haiku" />
      <div className="mk-card">
        <table className="mk-table">
          <thead><tr><th>Metric</th><th className="r">gpt-4o-mini</th><th className="r">claude-3-5-haiku</th></tr></thead>
          <tbody>{rows.map((r) => <tr key={r[0]}><td>{r[0]}</td><td className="r">{r[1]}</td><td className="r">{r[2]}</td></tr>)}</tbody>
        </table>
      </div>
    </>
  )
}

const SCREENS: Record<MockupKind, () => JSX.Element> = {
  plan: Plan, run: Run, score: Score, ledger: Ledger, models: Models, datasets: Datasets, connectors: Connectors, traces: Traces, compare: Compare,
}

export const RunportMockup: React.FC<{ kind: MockupKind }> = ({ kind }) => {
  const Screen = SCREENS[kind]
  return (
    <Shell kind={kind}>
      <Screen />
    </Shell>
  )
}

export const MOCKUP_SIZE = { width: 680, height: 700 }
