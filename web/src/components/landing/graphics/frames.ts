// Pure, time-based frame logic for the bento card graphics. The React
// components only render what these functions return, so the behaviour is
// unit-tested in web/tests/frames.test.ts (no DOM needed). Under reduced motion
// every function returns one static frame that still carries all the
// information the animation shows.
//
// Explicit .ts extensions so `node --experimental-strip-types` can run the tests.
import { CONNECTORS, type ConnectorStatus } from '../../../data/connectors.ts'
import { BUDGET_DEFAULTS, PLAN_FINGERPRINTS, SPEND_STEPS, formatUsd } from '../../../data/sampleRun.ts'

// ---------- 1. targets orbit ----------

/** Seconds for one revolution of the inner and outer ring. */
export const ORBIT_PERIOD_S = [56, 80] as const

export interface OrbitTile {
  id: string
  name: string
  status: ConnectorStatus
  logo?: string
  /** 0 = inner ring (experimental), 1 = outer ring (supported). */
  ring: 0 | 1
  /** Starting angle in radians. */
  phase: number
}

/** One tile per connector in data/connectors.ts, spread evenly on its ring. */
export function orbitTiles(): OrbitTile[] {
  const tiles: OrbitTile[] = []
  for (const ring of [0, 1] as const) {
    const members = CONNECTORS.filter((c) => (ring === 1) === (c.status === 'supported'))
    members.forEach((c, i) => {
      tiles.push({ id: c.id, name: c.name, status: c.status, logo: c.logo, ring, phase: (i / members.length) * Math.PI * 2 + ring * 0.4 })
    })
  }
  return tiles
}

/** Angle of a tile at time t (seconds). Reduced motion: the starting angle, always. */
export function orbitAngle(tile: OrbitTile, tSec: number, reduced: boolean): number {
  if (reduced) return tile.phase
  const dir = tile.ring === 0 ? 1 : -1
  return tile.phase + dir * ((Math.PI * 2 * tSec) / ORBIT_PERIOD_S[tile.ring])
}

export function ellipsePoint(angle: number, rx: number, ry: number): { x: number; y: number } {
  return { x: Math.cos(angle) * rx, y: Math.sin(angle) * ry }
}

// ---------- 2. plan and approval ----------

/** Seconds each phase of the plan demo is shown. */
export const PLAN_PHASE_S = 3

export interface PlanFrame {
  /** Fingerprint of the current plan. */
  fingerprint: string
  /** Fingerprint the standing approval was given for. */
  approvedFor: string
  /** Approved only when the approval matches the current plan, never otherwise. */
  status: 'approved' | 'rejected'
  /** The superseded fingerprint shown on the dashed "stale" card. */
  stale: string
}

const fp = (k: number) => PLAN_FINGERPRINTS[((k % PLAN_FINGERPRINTS.length) + PLAN_FINGERPRINTS.length) % PLAN_FINGERPRINTS.length]

/**
 * Even phases: the plan is approved as it stands. Odd phases: the plan changed,
 * so the old approval is rejected until a new typed approval is given.
 * Reduced motion: the rejected phase, which shows both fingerprints at once.
 */
export function planFrame(tSec: number, reduced: boolean): PlanFrame {
  const phase = reduced ? 1 : Math.floor(Math.max(0, tSec) / PLAN_PHASE_S)
  const k = Math.floor(phase / 2)
  const changed = phase % 2 === 1
  const fingerprint = changed ? fp(k + 1) : fp(k)
  const approvedFor = fp(k)
  return {
    fingerprint,
    approvedFor,
    status: fingerprint === approvedFor ? 'approved' : 'rejected',
    stale: changed ? fp(k) : fp(k - 1),
  }
}

// ---------- 3. spend guard ----------

export const BUDGET_STEP_S = 1
export const BUDGET_HOLD_S = 2.6

export interface BudgetRow {
  id: string
  /** Amount as shown: a dollar figure, or an em dash when the cost is unavailable. */
  label: string
  counted: boolean
  blocked: boolean
}

export interface BudgetFrame {
  capUsd: number
  rows: BudgetRow[]
  /** Spend booked by the rows shown so far (blocked and unavailable rows excluded). */
  spentUsd: number
  blocked: boolean
}

/** Walk the sample requests against the per-run cap; the first one that would cross it is blocked. */
export function budgetPlan(steps = SPEND_STEPS, capUsd: number = BUDGET_DEFAULTS.perRunUsd): { rows: BudgetRow[]; spent: number[] } {
  const rows: BudgetRow[] = []
  const spent: number[] = []
  let total = 0
  for (const s of steps) {
    if (s.usd === null) {
      rows.push({ id: s.id, label: '—', counted: false, blocked: false })
    } else if (total + s.usd > capUsd + 1e-9) {
      rows.push({ id: s.id, label: formatUsd(s.usd), counted: false, blocked: true })
      spent.push(total)
      break
    } else {
      total += s.usd
      rows.push({ id: s.id, label: formatUsd(s.usd), counted: true, blocked: false })
    }
    spent.push(total)
  }
  return { rows, spent }
}

export const budgetLoopS = () => budgetPlan().rows.length * BUDGET_STEP_S + BUDGET_HOLD_S

/** Rows revealed one per second, then a hold on the blocked state, then repeat. Reduced motion: the final state. */
export function budgetFrame(tSec: number, reduced: boolean): BudgetFrame {
  const { rows, spent } = budgetPlan()
  const capUsd = BUDGET_DEFAULTS.perRunUsd
  const loop = budgetLoopS()
  const t = reduced ? loop : ((Math.max(0, tSec) % loop) + loop) % loop
  const shown = reduced ? rows.length : Math.min(rows.length, Math.floor(t / BUDGET_STEP_S) + 1)
  const visible = rows.slice(0, shown)
  return { capUsd, rows: visible, spentUsd: spent[shown - 1] ?? 0, blocked: visible.some((r) => r.blocked) }
}
