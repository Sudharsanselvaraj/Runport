// Behaviour of the bento card graphics (web/src/components/landing/graphics/frames.ts).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import {
  ORBIT_LOOP_S,
  PLAN_CHANGE_S,
  PLAN_LOOP_S,
  PLAN_MORPH_S,
  SPEND_FILL_S,
  SPEND_LOOP_S,
  orbitAngle,
  orbitCaption,
  orbitTiles,
  planFrame,
  spendFrame,
  spendPlan,
} from '../src/components/landing/graphics/frames.ts'
import { CONNECTORS, CONNECTOR_COUNTS } from '../src/data/connectors.ts'
import { BUDGET_DEFAULTS, CONFUSION, PLAN, PLAN_FINGERPRINTS, RESULTS, confusionTotals, perClassRecall } from '../src/data/sampleRun.ts'

function readmeTable(): Map<string, string> {
  const readme = readFileSync(new URL('../../docs/connectors/README.md', import.meta.url), 'utf8')
  const table = new Map<string, string>()
  for (const m of readme.matchAll(/^\| `([a-z0-9_]+)` \|[^|]*\| \**\*?(Stable|Experimental)\**\*? \|/gm)) {
    table.set(m[1], m[2] === 'Stable' ? 'supported' : 'experimental')
  }
  return table
}

test('connector data matches the status table in docs/connectors/README.md', () => {
  const table = readmeTable()
  assert.equal(table.size, 12)
  assert.deepEqual(new Map(CONNECTORS.map((c) => [c.id, c.status])), table)
})

test('connector counts and the orbit caption are computed from the data file', () => {
  const table = [...readmeTable().values()]
  assert.equal(CONNECTOR_COUNTS.supported, table.filter((s) => s === 'supported').length)
  assert.equal(CONNECTOR_COUNTS.experimental, table.filter((s) => s === 'experimental').length)
  assert.equal(orbitCaption(), `${CONNECTOR_COUNTS.supported} supported · ${CONNECTOR_COUNTS.experimental} experimental`)
})

test('orbit tiles are real connectors with their real status', () => {
  const table = readmeTable()
  const tiles = orbitTiles()
  assert.equal(tiles.length, 8)
  for (const t of tiles) assert.equal(t.status, table.get(t.id), t.id)
})

test('the orbit drifts one slot per loop and eases', () => {
  const t0 = orbitTiles()[0]
  const start = orbitAngle(t0, 0, false)
  const end = orbitAngle(t0, ORBIT_LOOP_S, false)
  assert.ok(Math.abs(Math.abs(end - start) - t0.slot) < 1e-9)
  const quarter = Math.abs(orbitAngle(t0, ORBIT_LOOP_S / 4, false) - start)
  assert.ok(quarter < t0.slot / 4, 'slow start (ease-in)')
})

test('Approved is never shown next to a changed fingerprint', () => {
  for (let t = 0; t < PLAN_LOOP_S * 3; t += 0.02) {
    const f = planFrame(t, false)
    if (f.status === 'approved') {
      assert.equal(f.shown, f.approvedFor, `t=${t.toFixed(2)}`)
      assert.equal(f.changed, false)
    }
    if (f.shown !== f.approvedFor) assert.notEqual(f.status, 'approved', `t=${t.toFixed(2)}`)
  }
})

test('the plan loop: approved, morph, rejected with a reason, reset', () => {
  const [A, B] = PLAN_FINGERPRINTS
  assert.equal(A.length, 12)
  assert.equal(B.length, 12)
  assert.deepEqual(planFrame(1, false), { shown: A, approvedFor: A, status: 'approved', changed: false, reason: null })
  const mid = planFrame(PLAN_CHANGE_S + PLAN_MORPH_S / 2, false)
  assert.equal(mid.status, 'checking')
  assert.notEqual(mid.shown, A)
  assert.notEqual(mid.shown, B)
  const done = planFrame(PLAN_CHANGE_S + PLAN_MORPH_S + 0.1, false)
  assert.equal(done.status, 'rejected')
  assert.equal(done.shown, B)
  assert.ok(done.reason?.includes(A.slice(0, 8)) && done.reason.includes(B.slice(0, 8)))
  assert.equal(planFrame(PLAN_LOOP_S + 0.5, false).status, 'approved')
})

test('the spend guard books up to the cap and blocks the next request before sending', () => {
  const { rows, bookedUsd, capUsd } = spendPlan()
  assert.equal(rows.length, 3)
  assert.equal(capUsd, BUDGET_DEFAULTS.perRunUsd)
  assert.ok(bookedUsd <= capUsd + 1e-9)
  assert.deepEqual(rows.map((r) => r.state), ['booked', 'booked', 'blocked'])
  for (const r of rows) assert.ok(!/^\$0\.0+$/.test(r.label))
})

test('the spend loop fills over 8 s, shows the block, holds, and resets', () => {
  assert.equal(spendFrame(0, false).valueUsd, 0)
  assert.equal(spendFrame(SPEND_FILL_S / 2, false).blocked, false)
  const end = spendFrame(SPEND_FILL_S + 0.1, false)
  assert.equal(end.blocked, true)
  assert.equal(end.valueUsd.toFixed(2), spendPlan().bookedUsd.toFixed(2))
  assert.ok(SPEND_LOOP_S >= 8 && SPEND_LOOP_S <= 12)
  assert.equal(spendFrame(SPEND_LOOP_S + 0.01, false).blocked, false)
})

test('an unpriced request renders as an em dash and is not counted', () => {
  const { rows, bookedUsd } = spendPlan([
    { id: 'a', usd: 0.4 },
    { id: 'b', usd: null },
    { id: 'c', usd: 0.7 },
  ])
  assert.equal(rows[1].label, '—')
  assert.equal(rows[1].state, 'unpriced')
  assert.equal(rows[2].state, 'blocked')
  assert.equal(bookedUsd, 0.4)
})

test('reduced motion renders one static final frame with all the information', () => {
  for (const t of orbitTiles()) assert.equal(orbitAngle(t, 37.5, true), orbitAngle(t, 0, true))
  assert.deepEqual(planFrame(0, true), planFrame(999, true))
  const p = planFrame(0, true)
  assert.equal(p.status, 'rejected')
  assert.notEqual(p.shown, p.approvedFor)
  assert.ok(p.reason)
  assert.deepEqual(spendFrame(0, true), spendFrame(123, true))
  const s = spendFrame(0, true)
  assert.equal(s.blocked, true)
  assert.ok(s.rows.every((r) => r.state !== 'queued'))
})

test('the confusion matrix agrees with the sample accuracy', () => {
  const { correct, total } = confusionTotals()
  assert.equal(total, PLAN.cases)
  assert.equal(correct, RESULTS['gpt-4o-mini'].correct)
  assert.equal(CONFUSION.length, 5)
  for (const r of perClassRecall()) assert.ok(r > 0 && r <= 100)
})
