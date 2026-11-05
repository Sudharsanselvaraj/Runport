// Behaviour of the bento card graphics (web/src/components/landing/graphics/frames.ts).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  BUDGET_STEP_S,
  PLAN_PHASE_S,
  budgetFrame,
  budgetLoopS,
  budgetPlan,
  orbitAngle,
  orbitTiles,
  planFrame,
} from '../src/components/landing/graphics/frames.ts'
import { CONFUSION, PLAN, RESULTS, confusionTotals, perClassRecall } from '../src/data/sampleRun.ts'

test('orbit tiles match the connector status table in docs/connectors/README.md', () => {
  const readme = readFileSync(new URL('../../docs/connectors/README.md', import.meta.url), 'utf8')
  const table = new Map<string, string>()
  for (const m of readme.matchAll(/^\| `([a-z0-9_]+)` \|[^|]*\| \**\*?(Stable|Experimental)\**\*? \|/gm)) {
    table.set(m[1], m[2] === 'Stable' ? 'supported' : 'experimental')
  }
  assert.ok(table.size >= 10, 'could not read the connector table')
  const tiles = orbitTiles()
  assert.deepEqual(new Map(tiles.map((t) => [t.id, t.status])), table)
  for (const t of tiles) assert.equal(t.ring, t.status === 'supported' ? 1 : 0)
})

test('the plan demo never shows an approval for a changed fingerprint', () => {
  for (let t = 0; t < PLAN_PHASE_S * 24; t += 0.25) {
    const f = planFrame(t, false)
    if (f.status === 'approved') assert.equal(f.approvedFor, f.fingerprint, `t=${t}`)
    if (f.fingerprint !== f.approvedFor) assert.equal(f.status, 'rejected', `t=${t}`)
  }
  // it does change: both states occur
  assert.equal(planFrame(0, false).status, 'approved')
  assert.equal(planFrame(PLAN_PHASE_S, false).status, 'rejected')
})

test('the spend guard blocks the request that would cross the cap, before booking it', () => {
  const { rows } = budgetPlan()
  const blocked = rows.filter((r) => r.blocked)
  assert.equal(blocked.length, 1)
  assert.equal(rows[rows.length - 1].blocked, true)
  const final = budgetFrame(0, true)
  assert.ok(final.spentUsd <= final.capUsd)
  assert.equal(final.blocked, true)
  // unavailable cost renders as an em dash and is not counted
  const unavailable = rows.filter((r) => r.label === '—')
  assert.ok(unavailable.length >= 1)
  for (const r of unavailable) assert.equal(r.counted, false)
  for (const r of rows) assert.ok(!/^\$0\.0+$/.test(r.label))
})

test('budget totals add up from the counted rows', () => {
  const f = budgetFrame(0, true)
  const sum = f.rows.filter((r) => r.counted).reduce((a, r) => a + Number(r.label.slice(1)), 0)
  assert.equal(sum.toFixed(4), f.spentUsd.toFixed(4))
})

test('the budget loop reveals one row per step and repeats', () => {
  assert.equal(budgetFrame(0, false).rows.length, 1)
  assert.equal(budgetFrame(BUDGET_STEP_S * 2 + 0.1, false).rows.length, 3)
  assert.equal(budgetFrame(budgetLoopS() + 0.1, false).rows.length, 1)
})

test('reduced motion renders one static frame with all the information', () => {
  const tiles = orbitTiles()
  for (const t of tiles) assert.equal(orbitAngle(t, 37.5, true), orbitAngle(t, 0, true))
  assert.deepEqual(planFrame(0, true), planFrame(999, true))
  const p = planFrame(0, true)
  assert.notEqual(p.fingerprint, p.approvedFor)
  assert.equal(p.status, 'rejected')
  assert.deepEqual(budgetFrame(0, true), budgetFrame(123, true))
  assert.equal(budgetFrame(0, true).rows.length, budgetPlan().rows.length)
})

test('the confusion matrix agrees with the sample accuracy', () => {
  const { correct, total } = confusionTotals()
  assert.equal(total, PLAN.cases)
  assert.equal(correct, RESULTS['gpt-4o-mini'].correct)
  assert.equal(CONFUSION.length, 5)
  for (const r of perClassRecall()) assert.ok(r > 0 && r <= 100)
})
