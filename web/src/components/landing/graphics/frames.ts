// Pure, time-based frame logic for the bento card graphics. The React
// components only render what these functions return, so the behaviour is
// unit-tested in web/tests/frames.test.ts (no DOM needed). Every card has one
// slow loop (8-12 s, ease-in-out). Under reduced motion every function returns
// one static final frame that still carries all the information.
//
// Explicit .ts extensions so `node --experimental-strip-types` can run the tests.
import { CONNECTORS, CONNECTOR_COUNTS, type ConnectorStatus } from '../../../data/connectors.ts'
import { BUDGET_DEFAULTS, PLAN_FINGERPRINTS, SPEND_STEPS, formatUsd } from '../../../data/sampleRun.ts'

/** Smooth 0..1 -> 0..1 ease-in-out. */
export const easeInOut = (x: number) => 0.5 - Math.cos(Math.PI * Math.min(1, Math.max(0, x))) / 2

const wrap = (t: number, loop: number) => ((Math.max(0, t) % loop) + loop) % loop

// ---------- 1. targets orbit ----------

/** One loop moves every tile one slot along its ring, easing in and out. */
export const ORBIT_LOOP_S = 12

/** The connectors shown on the rings: every supported one plus two experimental ones. */
export const ORBIT_IDS = ['openai_compat', 'openrouter', 'dify', 'http_workflow', 'python_target', 'ollama', 'langgraph', 'n8n']

export interface OrbitTile {
  id: string
  name: string
  status: ConnectorStatus
  logo?: string
  icon?: 'globe' | 'terminal'
  ring: 0 | 1
  /** Starting angle in radians. */
  phase: number
  /** Angle between neighbouring tiles on the same ring. */
  slot: number
}

export function orbitTiles(): OrbitTile[] {
  const picked = ORBIT_IDS.map((id) => {
    const c = CONNECTORS.find((x) => x.id === id)
    if (!c) throw new Error(`unknown connector ${id}`)
    return c
  })
  const rings: [typeof picked, typeof picked] = [picked.filter((_, i) => i % 2 === 1), picked.filter((_, i) => i % 2 === 0)]
  const tiles: OrbitTile[] = []
  rings.forEach((members, ring) => {
    const slot = (Math.PI * 2) / members.length
    members.forEach((c, i) => {
      tiles.push({ id: c.id, name: c.name, status: c.status, logo: c.logo, icon: c.icon, ring: ring as 0 | 1, phase: i * slot + ring * (slot / 2), slot })
    })
  })
  return tiles
}

/** "N supported · M experimental", computed from the connector data file. */
export const orbitCaption = () => `${CONNECTOR_COUNTS.supported} supported · ${CONNECTOR_COUNTS.experimental} experimental`

export function orbitAngle(tile: OrbitTile, tSec: number, reduced: boolean): number {
  if (reduced) return tile.phase
  const k = Math.floor(Math.max(0, tSec) / ORBIT_LOOP_S)
  const frac = wrap(tSec, ORBIT_LOOP_S) / ORBIT_LOOP_S
  const dir = tile.ring === 0 ? 1 : -1
  return tile.phase + dir * tile.slot * (k + easeInOut(frac))
}

export function ellipsePoint(angle: number, rx: number, ry: number): { x: number; y: number } {
  return { x: Math.cos(angle) * rx, y: Math.sin(angle) * ry }
}

// ---------- 2. plan and approval ----------

export const PLAN_LOOP_S = 10
/** When the plan changes, how long the fingerprint takes to morph, and when the verdict lands. */
export const PLAN_CHANGE_S = 4
export const PLAN_MORPH_S = 0.6

export type PlanStatus = 'approved' | 'checking' | 'rejected'

export interface PlanFrame {
  /** The fingerprint shown on the card (first 12 hex characters). */
  shown: string
  /** The fingerprint the standing approval was given for. */
  approvedFor: string
  status: PlanStatus
  /** True once the plan has changed in this loop. */
  changed: boolean
  /** One-line reason, only when rejected. */
  reason: string | null
}

const [FP_A, FP_B] = PLAN_FINGERPRINTS

/**
 * 0-4 s: approved for A. 4 s: the plan changes and the fingerprint morphs to B
 * character by character over 600 ms while the pill reads "checking" (never
 * "approved"). 4.6-10 s: rejected, with the reason. Then it resets.
 * Reduced motion: the rejected frame, which shows both fingerprints.
 */
export function planFrame(tSec: number, reduced: boolean): PlanFrame {
  const t = reduced ? PLAN_LOOP_S - 0.01 : wrap(tSec, PLAN_LOOP_S)
  if (t < PLAN_CHANGE_S) return { shown: FP_A, approvedFor: FP_A, status: 'approved', changed: false, reason: null }
  const m = (t - PLAN_CHANGE_S) / PLAN_MORPH_S
  if (m < 1) {
    // the first character changes the moment the plan does
    const n = Math.max(1, Math.ceil(m * FP_B.length))
    return { shown: FP_B.slice(0, n) + FP_A.slice(n), approvedFor: FP_A, status: 'checking', changed: true, reason: null }
  }
  return {
    shown: FP_B,
    approvedFor: FP_A,
    status: 'rejected',
    changed: true,
    reason: `approval was for sha256:${FP_A.slice(0, 8)}…, plan is now sha256:${FP_B.slice(0, 8)}…`,
  }
}

// ---------- 3. spend guard ----------

export const SPEND_FILL_S = 8
export const SPEND_HOLD_S = 1.5
export const SPEND_LOOP_S = SPEND_FILL_S + SPEND_HOLD_S

export type SpendRowState = 'queued' | 'booked' | 'unpriced' | 'blocked'

export interface SpendRow {
  id: string
  /** A dollar figure, or an em dash when the cost is unavailable. */
  label: string
  state: SpendRowState
}

export interface SpendFrame {
  capUsd: number
  /** Spend shown on the ring (counts only booked rows). */
  valueUsd: number
  rows: SpendRow[]
  blocked: boolean
}

/** Walk the sample requests against the per-run cap; the first that would cross it is blocked. */
export function spendPlan(steps = SPEND_STEPS, capUsd: number = BUDGET_DEFAULTS.perRunUsd) {
  let total = 0
  const rows: (SpendRow & { at: number })[] = []
  for (const s of steps) {
    if (s.usd === null) rows.push({ id: s.id, label: '—', state: 'unpriced', at: total })
    else if (total + s.usd > capUsd + 1e-9) rows.push({ id: s.id, label: formatUsd(s.usd, 2), state: 'blocked', at: total })
    else {
      total += s.usd
      rows.push({ id: s.id, label: formatUsd(s.usd, 2), state: 'booked', at: total })
    }
  }
  return { rows, bookedUsd: total, capUsd }
}

/**
 * The ring fills over 8 s (ease-in-out) to the booked total; each row appears
 * once the ring reaches it; at 8 s the blocked request shows, holds 1.5 s, and
 * the loop resets. Reduced motion: the final, blocked frame.
 */
export function spendFrame(tSec: number, reduced: boolean): SpendFrame {
  const { rows, bookedUsd, capUsd } = spendPlan()
  const t = reduced ? SPEND_LOOP_S : wrap(tSec, SPEND_LOOP_S)
  const fillDone = t >= SPEND_FILL_S
  const valueUsd = fillDone ? bookedUsd : bookedUsd * easeInOut(t / SPEND_FILL_S)
  const shown: SpendRow[] = rows.map((r) => {
    const reached = r.state === 'blocked' ? fillDone : valueUsd >= r.at - 1e-9 && (r.state !== 'booked' || valueUsd > 0)
    return reached ? { id: r.id, label: r.label, state: r.state } : { id: r.id, label: '', state: 'queued' }
  })
  return { capUsd, valueUsd, rows: shown, blocked: shown.some((r) => r.state === 'blocked') }
}
