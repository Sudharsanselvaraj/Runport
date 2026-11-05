// The one source of truth for every illustrative number on the landing page.
// Everything here is SAMPLE DATA and is labelled "Sample data" wherever it is
// shown. Derived figures (accuracy, intervals, costs, totals) are computed by the
// helpers below, so every mockup agrees and totals add up from the visible rows.
//
// Plain TypeScript (no enums, no imports) so `node --experimental-strip-types`
// can run the unit tests in web/tests/sampleRun.test.ts.

/** Default spend ceilings, copied from BudgetConfig in src/runport/core/workspace.py. */
export const BUDGET_DEFAULTS = { totalUsd: 5.0, perRunUsd: 1.0, perCaseUsd: 0.05 } as const

/** Cost provenance as shown on the page. ACTUAL-LOCAL follows docs/connectors/README.md (Ollama). */
export type Provenance = 'ACTUAL' | 'ESTIMATED' | 'UNRESOLVED' | 'UNAVAILABLE' | 'ACTUAL-LOCAL' | 'REPLAYED'

export interface Candidate {
  id: string
  route: string
  /** USD per 1M tokens; null when unpriced (local or workflow targets). */
  inPer1M: number | null
  outPer1M: number | null
  contextK: number | null
}

export interface CandidateResult {
  correct: number
  invalid: number
  p50Ms: number
  p95Ms: number
  /** Mean reported tokens per case; null when the target does not report usage. */
  tokensIn: number | null
  tokensOut: number | null
  provenance: Provenance
}

export const PLAN = {
  name: 'support-triage',
  version: 'v3',
  split: 'TEST',
  cases: 240,
  devCases: 120,
  labels: 5,
  template: 'triage_v3.txt',
  fingerprint: 'sha256:9f2c41d0…7be3e41a',
  datasetHash: 'sha256:c07a5e19…02df8b6c',
  dataset: 'support_triage.jsonl',
} as const

export const CANDIDATES: Candidate[] = [
  { id: 'gpt-4o-mini', route: 'openrouter', inPer1M: 0.15, outPer1M: 0.6, contextK: 128 },
  { id: 'claude-3-5-haiku', route: 'openrouter', inPer1M: 0.8, outPer1M: 4.0, contextK: 200 },
  { id: 'llama3.1:8b', route: 'ollama · local', inPer1M: null, outPer1M: null, contextK: 128 },
  { id: 'support-triage flow', route: 'dify · workflow', inPer1M: null, outPer1M: null, contextK: null },
]

export const RESULTS: Record<string, CandidateResult> = {
  'gpt-4o-mini': { correct: 219, invalid: 4, p50Ms: 402, p95Ms: 1620, tokensIn: 214, tokensOut: 54, provenance: 'ESTIMATED' },
  'claude-3-5-haiku': { correct: 213, invalid: 2, p50Ms: 671, p95Ms: 2140, tokensIn: 214, tokensOut: 54, provenance: 'ACTUAL' },
  'llama3.1:8b': { correct: 178, invalid: 11, p50Ms: 1210, p95Ms: 3100, tokensIn: 221, tokensOut: 61, provenance: 'ACTUAL-LOCAL' },
}

/** Model-to-model agreement between run A and run B. Reported as agreement, never accuracy. */
export const AGREEMENT = { a: 'gpt-4o-mini', b: 'llama3.1:8b', kappa: 0.61 } as const

/** Extra scorecard figures for run A (sample). */
export const SCORE_EXTRAS = {
  macroF1: 0.897,
  brier: 0.071,
  perClass: [
    ['billing', 94],
    ['tech_support', 92],
    ['account', 89],
    ['shipping', 90],
    ['other', 81],
  ] as [string, number][],
}

export const candidate = (id: string): Candidate => {
  const c = CANDIDATES.find((x) => x.id === id)
  if (!c) throw new Error(`unknown sample candidate ${id}`)
  return c
}

// ---------- helpers ----------

/** Wilson score interval for k successes out of n, as proportions. */
export function wilson(k: number, n: number, z = 1.96): [number, number] {
  if (n <= 0) throw new Error('n must be positive')
  const p = k / n
  const z2 = z * z
  const denom = 1 + z2 / n
  const centre = (p + z2 / (2 * n)) / denom
  const half = (z * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))) / denom
  return [centre - half, centre + half]
}

export const pct = (k: number, n: number, digits = 1) => `${((k / n) * 100).toFixed(digits)}%`

/** Catalog cost of one case, or null when the target is unpriced or usage is unknown. */
export function costPerCaseUsd(c: Candidate, tokensIn: number | null, tokensOut: number | null): number | null {
  if (c.inPer1M === null || c.outPer1M === null || tokensIn === null || tokensOut === null) return null
  return (tokensIn * c.inPer1M + tokensOut * c.outPer1M) / 1_000_000
}

/** Cost of the whole plan for a candidate, or null when it cannot be priced. */
export function runCostUsd(id: string): number | null {
  const r = RESULTS[id]
  if (!r) return null
  const per = costPerCaseUsd(candidate(id), r.tokensIn, r.tokensOut)
  return per === null ? null : per * PLAN.cases
}

export function formatUsd(v: number, digits = 4): string {
  return `$${v.toFixed(digits)}`
}

export interface LedgerRow {
  run: string
  target: string
  provenance: Provenance
  /** USD, or null when the truth is unknown (UNRESOLVED) or there is no API spend. */
  amountUsd: number | null
}

/** Only provider-billed amounts with a known value count toward spend. */
export const countsTowardSpend = (p: Provenance) => p === 'ACTUAL' || p === 'ESTIMATED'

export const LEDGER: LedgerRow[] = [
  { run: 'run-0412', target: 'gpt-4o-mini', provenance: 'ESTIMATED', amountUsd: runCostUsd('gpt-4o-mini') },
  { run: 'run-0412', target: 'claude-3-5-haiku', provenance: 'ACTUAL', amountUsd: runCostUsd('claude-3-5-haiku') },
  { run: 'run-0412', target: 'llama3.1:8b', provenance: 'ACTUAL-LOCAL', amountUsd: null },
  { run: 'run-0412', target: 'support-triage flow', provenance: 'UNRESOLVED', amountUsd: null },
  { run: 'run-0409', target: 'replay fixture', provenance: 'REPLAYED', amountUsd: null },
]

/** Sum of the rows that count toward spend. Unknown, local and replayed rows are excluded. */
export function spentUsd(rows: LedgerRow[]): number {
  return rows.reduce((sum, r) => (countsTowardSpend(r.provenance) && r.amountUsd !== null ? sum + r.amountUsd : sum), 0)
}

export const remainingUsd = (rows: LedgerRow[], totalUsd: number = BUDGET_DEFAULTS.totalUsd) => totalUsd - spentUsd(rows)

export const unresolvedCount = (rows: LedgerRow[]) => rows.filter((r) => r.provenance === 'UNRESOLVED').length

/**
 * What an amount cell shows. Unknown is not zero: UNRESOLVED and UNAVAILABLE show an
 * em dash, local runs show "local", replayed runs show "replay". Never $0.00.
 */
export function formatAmount(row: { provenance: Provenance; amountUsd: number | null }, digits = 4): string {
  if (row.provenance === 'ACTUAL-LOCAL') return 'local'
  if (row.provenance === 'REPLAYED') return 'replay'
  if (row.provenance === 'UNRESOLVED' || row.provenance === 'UNAVAILABLE' || row.amountUsd === null) return '—'
  return formatUsd(row.amountUsd, digits)
}

/** Secondary note for an amount cell, or null. */
export function amountNote(p: Provenance): string | null {
  if (p === 'ACTUAL-LOCAL') return 'no API spend'
  if (p === 'REPLAYED') return 'excluded from spend'
  if (p === 'UNRESOLVED') return 'blocks live runs'
  return null
}

/** Cost per 1,000 cases for the comparison tables. */
export function costPer1kCell(id: string): { provenance: Provenance; amountUsd: number | null } {
  const r = RESULTS[id]
  const per = r ? costPerCaseUsd(candidate(id), r.tokensIn, r.tokensOut) : null
  return { provenance: r ? r.provenance : 'UNAVAILABLE', amountUsd: per === null ? null : per * 1000 }
}

// ---------- the live run shown in the walkthrough and the hero ----------

export const LIVE_RUN = {
  id: 'run-0412',
  done: 132,
  total: PLAN.cases,
  // case, target, latency ms, tokens in, tokens out
  events: [
    ['case-132', 'gpt-4o-mini', 412, 214, 54],
    ['case-131', 'claude-3-5-haiku', 688, 214, 54],
    ['case-131', 'llama3.1:8b', 1210, 221, 61],
    ['case-130', 'support-triage flow', 2040, null, null],
    ['case-130', 'gpt-4o-mini', 397, 216, 52],
  ] as [string, string, number, number | null, number | null][],
}

export function eventCell(target: string, tokensIn: number | null, tokensOut: number | null): { provenance: Provenance; amountUsd: number | null } {
  if (target === 'support-triage flow') return { provenance: 'UNRESOLVED', amountUsd: null }
  const r = RESULTS[target]
  const provenance: Provenance = r ? r.provenance : 'UNAVAILABLE'
  if (provenance === 'ACTUAL-LOCAL') return { provenance, amountUsd: null }
  return { provenance, amountUsd: costPerCaseUsd(candidate(target), tokensIn, tokensOut) }
}

// ---------- the trace in the integrations section ----------

export const TRACE = {
  id: 'run-3f9a2c1e',
  target: 'gpt-4o-mini',
  via: 'OpenRouter',
  elapsed: '3m 12s',
  cases: PLAN.cases,
  rows: [
    { id: 'case-001', status: 'success', ms: 1120 },
    { id: 'case-002', status: 'success', ms: 840 },
    { id: 'case-003', status: 'invalid_output', ms: 1620 },
    { id: 'case-004', status: 'success', ms: 410 },
    { id: 'case-005', status: 'timeout', ms: 2000 },
  ] as { id: string; status: 'success' | 'invalid_output' | 'timeout' | 'failed'; ms: number }[],
}

// ---------- results card: confusion matrix for run A (rows = actual, columns = predicted) ----------

export const CLASSES = ['billing', 'tech_support', 'account', 'shipping', 'other'] as const

export const CONFUSION: number[][] = [
  [60, 2, 1, 1, 0],
  [2, 55, 2, 0, 1],
  [2, 2, 41, 0, 1],
  [1, 0, 1, 36, 2],
  [1, 1, 0, 1, 27],
]

/** Per-class recall (correct / actual), in percent, from the confusion matrix. */
export const perClassRecall = (m: number[][] = CONFUSION) => m.map((row, i) => (row[i] / row.reduce((a, b) => a + b, 0)) * 100)

export const confusionTotals = (m: number[][] = CONFUSION) => ({
  correct: m.reduce((s, row, i) => s + row[i], 0),
  total: m.reduce((s, row) => s + row.reduce((a, b) => a + b, 0), 0),
})

// ---------- spend guard card: requests checked against the per-run ceiling ----------

/**
 * Estimated cost of each request in a sample run, in order. null = the target
 * reports no price (shown as an em dash, not counted). The ceiling is
 * BUDGET_DEFAULTS.perRunUsd; the last request would cross it and is blocked
 * before it is sent.
 */
export const SPEND_STEPS: { id: string; usd: number | null }[] = [
  { id: 'req-01', usd: 0.21 },
  { id: 'req-02', usd: 0.18 },
  { id: 'req-03', usd: null },
  { id: 'req-04', usd: 0.24 },
  { id: 'req-05', usd: 0.19 },
  { id: 'req-06', usd: 0.22 },
]

// ---------- plan card: fingerprints the approval demo cycles through ----------

export const PLAN_FINGERPRINTS = ['9f2c41d0', 'b71e09a4', '3c58d2f7'] as const
