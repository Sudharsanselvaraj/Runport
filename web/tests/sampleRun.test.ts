// Unit tests for the landing page sample-data helpers.
// Run with: npm test  (node --experimental-strip-types --test tests/)
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  BUDGET_DEFAULTS,
  LEDGER,
  LIVE_RUN,
  RESULTS,
  amountNote,
  costPer1kCell,
  eventCell,
  formatAmount,
  formatUsd,
  remainingUsd,
  spentUsd,
  unresolvedCount,
  wilson,
} from '../src/data/sampleRun.ts'

test('budget defaults match src/runport/core/workspace.py', () => {
  assert.deepEqual({ ...BUDGET_DEFAULTS }, { totalUsd: 5.0, perRunUsd: 1.0, perCaseUsd: 0.05 })
})

test('unknown is not zero: no amount cell ever renders $0.00', () => {
  for (const row of LEDGER) {
    const shown = formatAmount(row)
    assert.ok(!/^\$0\.0+$/.test(shown), `${row.target} rendered ${shown}`)
  }
  assert.equal(formatAmount({ provenance: 'UNRESOLVED', amountUsd: null }), '—')
  assert.equal(formatAmount({ provenance: 'UNAVAILABLE', amountUsd: null }), '—')
  assert.equal(formatAmount({ provenance: 'UNAVAILABLE', amountUsd: 0 }), '—')
  assert.equal(formatAmount({ provenance: 'ACTUAL-LOCAL', amountUsd: null }), 'local')
  assert.equal(formatAmount({ provenance: 'REPLAYED', amountUsd: 0 }), 'replay')
  assert.equal(amountNote('ACTUAL-LOCAL'), 'no API spend')
  assert.equal(amountNote('REPLAYED'), 'excluded from spend')
})

test('ledger total adds up exactly from the visible rows', () => {
  const visibleSum = LEDGER.filter((r) => r.provenance === 'ACTUAL' || r.provenance === 'ESTIMATED')
    .map((r) => Number(formatAmount(r).slice(1)))
    .reduce((a, b) => a + b, 0)
  assert.equal(formatUsd(spentUsd(LEDGER)), formatUsd(visibleSum))
  assert.equal(formatUsd(spentUsd(LEDGER)), '$0.1084')
  assert.equal(formatUsd(remainingUsd(LEDGER)), '$4.8916')
  assert.equal(
    Number(formatUsd(spentUsd(LEDGER)).slice(1)) + Number(formatUsd(remainingUsd(LEDGER)).slice(1)),
    BUDGET_DEFAULTS.totalUsd,
  )
})

test('unresolved, local and replayed rows are excluded from spend', () => {
  const excluded = LEDGER.filter((r) => ['UNRESOLVED', 'ACTUAL-LOCAL', 'REPLAYED'].includes(r.provenance))
  assert.equal(excluded.length, 3)
  assert.equal(spentUsd(excluded), 0)
  assert.equal(unresolvedCount(LEDGER), 1)
})

test('the sample run stays inside the default per-run ceiling', () => {
  assert.ok(spentUsd(LEDGER.filter((r) => r.run === 'run-0412')) < BUDGET_DEFAULTS.perRunUsd)
  for (const [, target, , tin, tout] of LIVE_RUN.events) {
    const cell = eventCell(target, tin, tout)
    if (cell.amountUsd !== null) assert.ok(cell.amountUsd < BUDGET_DEFAULTS.perCaseUsd)
  }
})

test('local and workflow targets have no price, never a zero price', () => {
  assert.equal(costPer1kCell('llama3.1:8b').amountUsd, null)
  assert.equal(formatAmount(costPer1kCell('llama3.1:8b')), 'local')
  assert.equal(eventCell('support-triage flow', null, null).provenance, 'UNRESOLVED')
  assert.equal(formatAmount(eventCell('support-triage flow', null, null)), '—')
})

test('Wilson interval for the sample accuracy', () => {
  const r = RESULTS['gpt-4o-mini']
  const [lo, hi] = wilson(r.correct, 240)
  assert.equal(lo.toFixed(4), '0.8699')
  assert.equal(hi.toFixed(4), '0.9421')
  assert.throws(() => wilson(1, 0))
})
