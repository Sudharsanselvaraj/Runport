import React, { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { useInView, useReducedMotion } from 'framer-motion'
import {
  AlertTriangle,
  Check,
  Clock,
  Globe,
  Info,
  Pause,
  Play,
  Server,
} from 'lucide-react'
import { LANDING_CONTENT } from '../../data/landingContent'
import { Reveal } from './motion'
import '../../styles/story.css'

// ============================================================================
// STAGE 1: INTEGRATION CONTRACTS & METADATA
// ============================================================================

interface IntegrationItem {
  id: string
  name: string
  status: 'native' | 'compat' | 'exp'
  via: string
  evidence: string
  logo?: string
  icon?: 'globe' | 'server'
}

interface IntegrationGroup {
  key: string
  label: string
  role: string
  items: IntegrationItem[]
}

const INTEGRATION_GROUPS: IntegrationGroup[] = [
  {
    key: 'providers',
    label: 'Model Providers',
    role: 'Hosted LLM endpoints',
    items: [
      {
        id: 'openai',
        name: 'OpenAI',
        status: 'native',
        via: 'Direct API',
        evidence: 'connectors/openai_compat.py (api.openai.com)',
        logo: '/assets/landing/logos/openai.svg',
      },
      {
        id: 'openrouter',
        name: 'OpenRouter',
        status: 'native',
        via: 'Gateway adapter',
        evidence: 'providers/openrouter.py',
        logo: '/assets/landing/logos/openrouter.svg',
      },
      {
        id: 'anthropic',
        name: 'Anthropic',
        status: 'compat',
        via: 'via OpenRouter',
        evidence: 'Routed by model ID through providers/openrouter.py',
        logo: '/assets/landing/logos/anthropic.svg',
      },
      {
        id: 'gemini',
        name: 'Gemini',
        status: 'compat',
        via: 'via OpenRouter',
        evidence: 'Default CLI model google/gemini-* via OpenRouter',
        logo: '/assets/landing/logos/gemini.svg',
      },
      {
        id: 'openai-compat',
        name: 'OpenAI-compat',
        status: 'native',
        via: 'Any standard server',
        evidence: 'OpenAICompatConnector(base_url=...)',
        icon: 'globe',
      },
    ],
  },
  {
    key: 'workflows',
    label: 'Workflows & Agents',
    role: 'Orchestrated targets',
    items: [
      {
        id: 'dify',
        name: 'Dify',
        status: 'native',
        via: 'Workflow API',
        evidence: 'connectors/dify.py',
        logo: '/assets/landing/logos/dify.svg',
      },
      {
        id: 'langgraph',
        name: 'LangGraph',
        status: 'exp',
        via: 'Graph Runner (exp)',
        evidence: 'connectors/langgraph.py (experimental)',
        logo: '/assets/landing/logos/langgraph.svg',
      },
      {
        id: 'mcp',
        name: 'MCP Server',
        status: 'native',
        via: 'Model Context Protocol',
        evidence: 'connectors/mcp.py & mcp_server.py',
        icon: 'server',
      },
    ],
  },
  {
    key: 'local',
    label: 'Local & Runtime',
    role: 'Local serving & code',
    items: [
      {
        id: 'ollama',
        name: 'Ollama',
        status: 'native',
        via: 'Local API',
        evidence: 'connectors/ollama.py',
        logo: '/assets/landing/logos/ollama.svg',
      },
      {
        id: 'vllm',
        name: 'vLLM',
        status: 'compat',
        via: 'OpenAI-compatible server',
        evidence: 'Self-hosted vLLM serving /v1/chat/completions',
        logo: '/assets/landing/logos/vllm.svg',
      },
      {
        id: 'python',
        name: 'Python callable',
        status: 'native',
        via: 'Python target',
        evidence: 'connectors/python_target.py (PythonCallableTarget)',
        logo: '/assets/landing/logos/python.svg',
      },
    ],
  },
]

// ============================================================================
// STAGE 2: THE SEVEN SEQUENTIAL RUNNER SAFEGUARDS
// ============================================================================

interface Safeguard {
  step: number
  id: string
  name: string
  badge: string
  desc: string
  rule: string
}

const SAFEGUARDS: Safeguard[] = [
  {
    step: 1,
    id: 'auth',
    name: 'Authorization',
    badge: 'API KEY / RBAC',
    desc: 'Validates caller identity, credentials, and tenant access gates.',
    rule: 'Never bypass or spoof authentication.',
  },
  {
    step: 2,
    id: 'privacy',
    name: 'Privacy Gate',
    badge: 'SECRET REDACTION',
    desc: 'Scans and scrubs API keys, bearer tokens, and private secrets from payloads.',
    rule: 'Zero secrets leak into trace logs or exports.',
  },
  {
    step: 3,
    id: 'budget',
    name: 'Preflight Budget',
    badge: 'FAIL-CLOSED CAP',
    desc: 'Calculates maximum worst-case cost against per-run and per-case caps.',
    rule: 'Blocks request before transport if ceiling exceeded.',
  },
  {
    step: 4,
    id: 'transport',
    name: 'Transport',
    badge: 'BOUNDED RETRIES',
    desc: 'Executes HTTP/local request with bounded retry and timeout limits.',
    rule: 'Records exact wire latency without simulation.',
  },
  {
    step: 5,
    id: 'validation',
    name: 'Validation',
    badge: 'STRICT SCHEMA',
    desc: 'Validates response payload structure, JSON schema, and required fields.',
    rule: 'Catches malformed outputs before persisting results.',
  },
  {
    step: 6,
    id: 'persistence',
    name: 'Persistence',
    badge: 'SQLITE WAL TRACE',
    desc: 'Writes canonical trace records with cryptographic SHA-256 fingerprint.',
    rule: 'Append-only storage preserves immutable audit trail.',
  },
  {
    step: 7,
    id: 'spend',
    name: 'Spend Booking',
    badge: 'APPEND-ONLY LEDGER',
    desc: 'Books spend with fixed provenance (ACTUAL, ESTIMATED, or UNRESOLVED).',
    rule: 'Unresolved spend blocks future runs fail-closed.',
  },
]

// ============================================================================
// STAGE 3: EXECUTION TRACE CASES (WATERFALL)
// ============================================================================

interface TraceCase {
  id: string
  target: string
  route: string
  startPct: number
  durationPct: number
  ms: number
  tokens: number | null
  cost: string
  provenance: string
  status: 'success' | 'invalid' | 'timeout'
  statusLabel: string
  detail: string
}

const TRACE_CASES: TraceCase[] = [
  {
    id: 'case-130',
    target: 'gpt-4o-mini',
    route: 'openrouter',
    startPct: 4,
    durationPct: 18,
    ms: 397,
    tokens: 268,
    cost: '$0.0001',
    provenance: 'ESTIMATED',
    status: 'success',
    statusLabel: 'PASS',
    detail: 'Classification match · latency 397ms · 268 tokens billed at $0.15/$0.60 per 1M',
  },
  {
    id: 'case-131',
    target: 'claude-3-5-haiku',
    route: 'openrouter',
    startPct: 10,
    durationPct: 32,
    ms: 688,
    tokens: 268,
    cost: '$0.0004',
    provenance: 'ACTUAL',
    status: 'success',
    statusLabel: 'PASS',
    detail: 'Classification match · provider-reported actual spend $0.0004 · 688ms',
  },
  {
    id: 'case-131',
    target: 'llama3.1:8b',
    route: 'ollama · local',
    startPct: 16,
    durationPct: 54,
    ms: 1210,
    tokens: 282,
    cost: 'local',
    provenance: 'ACTUAL-LOCAL',
    status: 'success',
    statusLabel: 'PASS',
    detail: 'Local GPU inference · 1.21s · 282 tokens · $0.00 external API spend',
  },
  {
    id: 'case-132',
    target: 'support-triage flow',
    route: 'dify · workflow',
    startPct: 8,
    durationPct: 70,
    ms: 2450,
    tokens: null,
    cost: '—',
    provenance: 'UNRESOLVED',
    status: 'invalid',
    statusLabel: 'INVALID_OUTPUT',
    detail: 'Validation error: JSON missing required attribute "category" · booked as UNRESOLVED',
  },
  {
    id: 'case-133',
    target: 'langgraph-agent',
    route: 'langgraph · exp',
    startPct: 4,
    durationPct: 92,
    ms: 5000,
    tokens: null,
    cost: '—',
    provenance: 'UNAVAILABLE',
    status: 'timeout',
    statusLabel: 'TIMEOUT (5.0s)',
    detail: 'Transport timeout: exceeded bounded execution window (5000ms ceiling)',
  },
]

// ============================================================================
// STAGE 4: EVALUATION METRICS
// ============================================================================

interface EvalMetric {
  id: string
  label: string
  value: string
  ci: string
  badge: string
  note: string
  tooltip: string
}

const EVAL_METRICS: EvalMetric[] = [
  {
    id: 'acc',
    label: 'Accuracy',
    value: '91.3%',
    ci: 'Wilson 95% [87.0–94.2%]',
    badge: 'HUMAN GT',
    note: 'Supervised against approved annotations',
    tooltip: 'Supervised metric evaluated only on TEST split against human-approved labels. Model consensus is never accuracy.',
  },
  {
    id: 'p95',
    label: 'p95 Latency',
    value: '1.84s',
    ci: 'p50: 512ms · p90: 1.45s',
    badge: 'WIRE TIME',
    note: 'Wall-clock transport & execution',
    tooltip: '95th percentile end-to-end execution time captured directly by Transport stage.',
  },
  {
    id: 'cost',
    label: 'Cost / 1k Cases',
    value: '$0.82',
    ci: 'basis: ESTIMATED',
    badge: 'CATALOG RATE',
    note: 'Standardized rate × token volume',
    tooltip: 'Exact spend calculation using verified catalog rate × token volume with ESTIMATED provenance.',
  },
  {
    id: 'invalid',
    label: 'Invalid Output',
    value: '2.5%',
    ci: '1 of 40 cases failed schema',
    badge: 'VALIDATION',
    note: 'Strict JSON schema enforcement',
    tooltip: 'Rejection rate at Stage 5 Validation before persistence or spend booking.',
  },
  {
    id: 'kappa',
    label: 'Agreement κ',
    value: '0.61',
    ci: 'vs llama3.1:8b',
    badge: 'CONSENSUS',
    note: 'Inter-model agreement · NOT accuracy',
    tooltip: "Cohen's Kappa agreement between candidate models. Invariant: Agreement is never presented as accuracy.",
  },
  {
    id: 'unresolved',
    label: 'Unresolved Spend',
    value: '$0.00 booked',
    ci: '1 entry pending reconciliation',
    badge: 'FAIL-CLOSED',
    note: 'Blocks execution until resolved',
    tooltip: 'Unresolved spend blocks further runs fail-closed until reconciled via runport budget reconcile.',
  },
]

// Handles component for technical panel borders
const Handles: React.FC = () => (
  <>
    <i className="rp-cx-h is-tl" aria-hidden="true" />
    <i className="rp-cx-h is-tr" aria-hidden="true" />
    <i className="rp-cx-h is-bl" aria-hidden="true" />
    <i className="rp-cx-h is-br" aria-hidden="true" />
  </>
)

export const BenchmarkFlow: React.FC = () => {
  const reduce = useReducedMotion()
  const rootRef = useRef<HTMLDivElement>(null)
  const panelRef = useRef<HTMLDivElement>(null)
  const coreRef = useRef<HTMLDivElement>(null)
  const traceRef = useRef<HTMLDivElement>(null)
  const inView = useInView(rootRef, { margin: '-10% 0px -10% 0px' })

  // Playback timer states
  const [timeMs, setTimeMs] = useState(0)
  const [isPaused, setIsPaused] = useState(false)
  const [hoverPaused, setHoverPaused] = useState(false)
  const [selectedHover, setSelectedHover] = useState<{
    title: string
    body: string
    rule?: string
  } | null>(null)

  // Hovered item id to highlight specific connection
  const [hoveredIntegration, setHoveredIntegration] = useState<string | null>(null)

  // Dynamic SVG path coordinates
  const [svgPaths, setSvgPaths] = useState<{
    w: number
    h: number
    topLines: string[]
    midLine: string
  } | null>(null)

  const TOTAL_CYCLE_MS = 14500
  const activePlay = inView && !isPaused && !hoverPaused && !reduce

  // Animation timeline loop
  useEffect(() => {
    if (reduce) {
      setTimeMs(TOTAL_CYCLE_MS)
      return
    }
    if (!activePlay) return

    const interval = 50
    const timer = setInterval(() => {
      setTimeMs((prev) => {
        const next = prev + interval
        if (next >= TOTAL_CYCLE_MS) {
          return 0
        }
        return next
      })
    }, interval)

    return () => clearInterval(timer)
  }, [activePlay, reduce])

  // Derive animation stages from timeMs
  // 0 - 2.2s: Stage 1 Integrations
  // 2.2s - 5.8s: Stage 2 Core & 7 Safeguards
  // 5.8s - 9.8s: Stage 3 Trace Waterfall
  // 9.8s - 12.8s: Stage 4 Metrics
  // 12.8s - 14.5s: Hold & Savor
  const currentStage = reduce
    ? 4
    : timeMs < 2200
    ? 1
    : timeMs < 5800
    ? 2
    : timeMs < 9800
    ? 3
    : 4

  const isStage1On = reduce || timeMs >= 400
  const isLines1On = reduce || timeMs >= 1600 || hoveredIntegration !== null
  const isCoreOn = reduce || timeMs >= 2200
  const isTraceOn = reduce || timeMs >= 5800
  const isMetricsOn = reduce || timeMs >= 9800

  // Calculate active safeguard step (1..7) based on timeMs in [2400ms, 5400ms]
  const activeSgStep = reduce
    ? 7
    : timeMs < 2400
    ? 0
    : timeMs < 2800
    ? 1
    : timeMs < 3200
    ? 2
    : timeMs < 3600
    ? 3
    : timeMs < 4000
    ? 4
    : timeMs < 4500
    ? 5
    : timeMs < 5000
    ? 6
    : timeMs < 5800
    ? 7
    : 7

  // Calculate visible trace rows based on timeMs in [5800ms, 9600ms]
  const visibleTraceRows = reduce
    ? TRACE_CASES.length
    : timeMs < 5800
    ? 0
    : timeMs < 6400
    ? 1
    : timeMs < 7100
    ? 2
    : timeMs < 7800
    ? 3
    : timeMs < 8600
    ? 4
    : TRACE_CASES.length

  // Calculate visible metrics based on timeMs in [9800ms, 12500ms]
  const visibleMetricsCount = reduce
    ? EVAL_METRICS.length
    : timeMs < 9800
    ? 0
    : Math.min(EVAL_METRICS.length, Math.floor(((timeMs - 9800) / 2400) * EVAL_METRICS.length) + 1)

  // Measure SVG connectors from live DOM layout
  const measureSvg = useCallback(() => {
    const root = rootRef.current
    const panel = panelRef.current
    const core = coreRef.current
    const trace = traceRef.current
    if (!root || !panel || !core || !trace) return

    const R = root.getBoundingClientRect()
    const P = panel.getBoundingClientRect()
    const C = core.getBoundingClientRect()
    const T = trace.getBoundingClientRect()

    const rx = (v: number) => Math.round(v - R.left)
    const ry = (v: number) => Math.round(v - R.top)

    const coreCenterX = rx(C.left + C.width / 2)
    const coreTopY = ry(C.top)
    const coreBottomY = ry(C.bottom)

    // Stage 1 -> Stage 2: 3 feeder bracket lines converging into Runport core
    const panelBottomY = ry(P.bottom)
    const midFeederY = panelBottomY + (coreTopY - panelBottomY) * 0.45

    const col1X = rx(P.left + P.width * 0.22)
    const col2X = rx(P.left + P.width * 0.5)
    const col3X = rx(P.left + P.width * 0.78)

    const topLines: string[] = [
      `M ${col1X} ${panelBottomY} L ${col1X} ${midFeederY} L ${coreCenterX} ${midFeederY}`,
      `M ${col2X} ${panelBottomY} L ${col2X} ${midFeederY}`,
      `M ${col3X} ${panelBottomY} L ${col3X} ${midFeederY} L ${coreCenterX} ${midFeederY}`,
      `M ${coreCenterX} ${midFeederY} L ${coreCenterX} ${coreTopY - 4}`,
    ]

    // Stage 2 -> Stage 3: line from safeguards into trace timeline
    const midLine = `M ${coreCenterX} ${coreBottomY + 4} L ${coreCenterX} ${ry(T.top) - 2}`

    setSvgPaths({
      w: Math.round(R.width),
      h: Math.round(R.height),
      topLines,
      midLine,
    })
  }, [])

  useLayoutEffect(() => {
    measureSvg()
    const ro = new ResizeObserver(measureSvg)
    if (rootRef.current) ro.observe(rootRef.current)
    return () => ro.disconnect()
  }, [measureSvg])

  // Jump to specific stage
  const jumpToStage = (stageIdx: number) => {
    if (stageIdx === 1) setTimeMs(0)
    else if (stageIdx === 2) setTimeMs(2300)
    else if (stageIdx === 3) setTimeMs(5900)
    else if (stageIdx === 4) setTimeMs(9900)
  }

  return (
    <div
      ref={rootRef}
      className="rp-story"
      onPointerEnter={() => setHoverPaused(true)}
      onPointerLeave={() => {
        setHoverPaused(false)
        setSelectedHover(null)
        setHoveredIntegration(null)
      }}
    >
      {/* Dynamic Marching SVG Dashed Connectors */}
      {svgPaths && (
        <svg
          className="rp-story-svg-overlay"
          width={svgPaths.w}
          height={svgPaths.h}
          viewBox={`0 0 ${svgPaths.w} ${svgPaths.h}`}
          aria-hidden="true"
        >
          {svgPaths.topLines.map((d, i) => (
            <path
              key={`top-${i}`}
              d={d}
              className={isLines1On ? 'is-active' : undefined}
            />
          ))}
          <path
            d={svgPaths.midLine}
            className={isTraceOn ? 'is-active' : undefined}
          />
        </svg>
      )}

      {/* Top Controller Bar: Stage Pills & Play/Pause */}
      <div className="rp-story-ctrl">
        <div className="rp-story-pills" role="tablist" aria-label="Execution story stages">
          {[
            { id: 1, label: '01 Integrations' },
            { id: 2, label: '02 Safeguards' },
            { id: 3, label: '03 Trace Waterfall' },
            { id: 4, label: '04 Evaluation' },
          ].map((pill) => (
            <button
              key={pill.id}
              type="button"
              className={`rp-story-pill ${currentStage === pill.id ? 'is-active' : ''}`}
              onClick={() => jumpToStage(pill.id)}
            >
              <span>{pill.label}</span>
            </button>
          ))}
        </div>

        {!reduce && (
          <button
            type="button"
            className="rp-story-pause"
            onClick={() => setIsPaused((p) => !p)}
            aria-label={isPaused ? 'Resume story animation' : 'Pause story animation'}
            title={isPaused ? 'Resume animation' : 'Pause animation'}
          >
            {isPaused ? <Play size={13} /> : <Pause size={13} />}
          </button>
        )}
      </div>

      {/* ====================================================================
          STAGE 1: INTEGRATIONS PANEL
          ==================================================================== */}
      <div ref={panelRef} className="rp-story-panel">
        <Handles />
        <div className="rp-story-groups">
          {INTEGRATION_GROUPS.map((group) => (
            <div key={group.key} className="rp-story-group">
              <div className="rp-story-group-head">
                <span className="rp-story-group-label">{group.label}</span>
                <span className="rp-story-group-role">{group.role}</span>
              </div>
              <div className="rp-story-tiles">
                {group.items.map((item) => {
                  const isHovered = hoveredIntegration === item.id
                  return (
                    <div
                      key={item.id}
                      className={`rp-story-tile ${isHovered || isStage1On ? 'is-active' : ''}`}
                      onPointerEnter={() => {
                        setHoveredIntegration(item.id)
                        setSelectedHover({
                          title: item.name,
                          body: `${item.via} · ${item.evidence}`,
                          rule: `Status: ${item.status === 'exp' ? 'Experimental connector' : item.status === 'compat' ? 'Standard compatibility' : 'Native connector'}`,
                        })
                      }}
                      onPointerLeave={() => {
                        setHoveredIntegration(null)
                        setSelectedHover(null)
                      }}
                    >
                      {item.logo ? (
                        <img src={item.logo} alt="" loading="lazy" />
                      ) : item.icon === 'server' ? (
                        <Server size={14} className="rp-story-icon" />
                      ) : (
                        <Globe size={14} className="rp-story-icon" />
                      )}
                      <span>{item.name}</span>
                      {item.status === 'exp' && (
                        <span className="rp-story-badge-exp">EXP</span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ====================================================================
          STAGE 2: RUNPORT EXECUTION CORE & 7 SAFEGUARDS
          ==================================================================== */}
      <div className="rp-story-core-section">
        {/* Core Emblem Badge */}
        <div
          ref={coreRef}
          className={`rp-story-core-badge ${isCoreOn ? 'is-on' : ''}`}
          onPointerEnter={() =>
            setSelectedHover({
              title: 'Runport Execution Engine',
              body: 'Coordinates model execution, enforces fail-closed spend caps, and records immutable traces.',
              rule: 'Strict Runner Guard Order enforced on every case.',
            })
          }
        >
          <img src="/assets/landing/runport-emblem.png" alt="Runport" />
          <div>
            <div className="rp-story-core-title">Runport Execution Core</div>
            <div className="rp-story-core-sub">SHA-256 Plan Fingerprint · Fail-Closed Ledger</div>
          </div>
        </div>

        {/* The 7 Sequential Safeguards Rail */}
        <div className="rp-story-safeguards">
          <div className="rp-story-safeguards-track" aria-hidden="true" />
          {SAFEGUARDS.map((sg) => {
            const isActive = activeSgStep === sg.step
            const isDone = activeSgStep > sg.step || reduce
            return (
              <div
                key={sg.id}
                className={`rp-story-sg-item ${isActive ? 'is-active' : ''} ${isDone ? 'is-done' : ''}`}
                onPointerEnter={() =>
                  setSelectedHover({
                    title: `Stage ${sg.step}: ${sg.name}`,
                    body: sg.desc,
                    rule: `Invariant: ${sg.rule}`,
                  })
                }
                onPointerLeave={() => setSelectedHover(null)}
              >
                <div className="rp-story-sg-dot">
                  {isDone ? <Check size={11} strokeWidth={3} /> : sg.step}
                </div>
                <span className="rp-story-sg-name">{sg.name}</span>
              </div>
            )
          })}
        </div>
      </div>

      {/* ====================================================================
          STAGE 3: EXECUTION TRACE TIMELINE (WATERFALL)
          ==================================================================== */}
      <div ref={traceRef} className="rp-story-trace">
        <Handles />
        {/* Trace Header */}
        <div className="rp-story-trace-head">
          <div className="rp-story-trace-meta">
            <span className="rp-story-run-id">run-0412</span>
            <span className="rp-story-fp">sha256:9f2c41d0..7be3e41a</span>
            <span className="rp-story-crumb">support-triage-v3</span>
          </div>
          <div className="rp-story-trace-stats">
            {isTraceOn ? '240 cases · 5 in trace · 1.84s wall-clock' : 'Queued'}
          </div>
        </div>

        {/* Time ruler */}
        <div className="rp-story-time-header">
          <span>CASE / TARGET</span>
          <div className="rp-story-time-ruler">
            <span>0ms</span>
            <span>500ms</span>
            <span>1.0s</span>
            <span>2.0s</span>
            <span>5.0s</span>
          </div>
          <span style={{ textAlign: 'right' }}>LATENCY</span>
        </div>

        {/* Waterfall Rows */}
        <div className="rp-story-rows">
          {/* Parent Run Row */}
          <div
            className="rp-story-row is-parent"
            onPointerEnter={() =>
              setSelectedHover({
                title: 'Parent Execution: run-0412',
                body: 'Orchestrated benchmark run across 4 candidate targets with fail-closed spend cap.',
                rule: 'Wall-clock duration: 1.84s · Total cases: 240',
              })
            }
          >
            <div className="rp-story-row-info">
              <span className="rp-story-parent-dot" />
              <span className="rp-story-row-name">run-0412</span>
              <span className="rp-story-row-route">support-triage</span>
            </div>
            <div className="rp-story-bar-track">
              <div
                className="rp-story-bar"
                style={{
                  left: '0%',
                  width: isTraceOn ? '100%' : '0%',
                }}
              />
            </div>
            <div className="rp-story-row-status">
              <span>1.84s</span>
            </div>
          </div>

          {/* Child Case Execution Rows */}
          {TRACE_CASES.slice(0, visibleTraceRows).map((c) => (
            <div
              key={c.id + c.target}
              className="rp-story-row"
              onPointerEnter={() =>
                setSelectedHover({
                  title: `${c.id} · ${c.target}`,
                  body: c.detail,
                  rule: `Provenance: ${c.provenance} · Tokens: ${c.tokens ?? '—'} · Status: ${c.statusLabel}`,
                })
              }
              onPointerLeave={() => setSelectedHover(null)}
            >
              <div className="rp-story-row-info" style={{ paddingLeft: 14 }}>
                <span className="rp-story-child-branch">↳</span>
                <span className="rp-story-row-name">{c.id}</span>
                <span className="rp-story-row-route">{c.target}</span>
              </div>
              <div className="rp-story-bar-track">
                <div
                  className={`rp-story-bar is-${c.status}`}
                  style={{
                    left: `${c.startPct}%`,
                    width: isTraceOn ? `${c.durationPct}%` : '0%',
                  }}
                />
              </div>
              <div className="rp-story-row-status">
                <span className={`rp-story-badge is-${c.status}`}>
                  {c.status === 'success' ? (
                    `${c.ms}ms`
                  ) : c.status === 'invalid' ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                      <AlertTriangle size={10} /> SCHEMA
                    </span>
                  ) : (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                      <Clock size={10} /> TIMEOUT
                    </span>
                  )}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ====================================================================
          STAGE 4: EVALUATION METRICS CARDS
          ==================================================================== */}
      <div className="rp-story-metrics">
        {EVAL_METRICS.slice(0, isMetricsOn ? visibleMetricsCount : 0).map((m) => (
          <div
            key={m.id}
            className="rp-story-metric"
            onPointerEnter={() =>
              setSelectedHover({
                title: m.label,
                body: m.tooltip,
                rule: `${m.ci} · Badge: ${m.badge}`,
              })
            }
            onPointerLeave={() => setSelectedHover(null)}
          >
            <div className="rp-story-metric-head">
              <span className="rp-story-metric-label">{m.label}</span>
              <span className="rp-story-metric-tag">{m.badge}</span>
            </div>
            <div className="rp-story-metric-value">{m.value}</div>
            <div className="rp-story-metric-ci" title={m.ci}>
              {m.ci}
            </div>
          </div>
        ))}
      </div>

      {/* Atmospheric Bottom Gradient Fade */}
      <div className="rp-story-fade" aria-hidden="true" />

      {/* Interactive Tooltip Popover */}
      {selectedHover && (
        <div className="rp-story-popover" style={{ left: '50%', transform: 'translateX(-50%)', bottom: 30 }}>
          <div className="rp-story-pop-title">
            <Info size={12} className="rp-story-acc" />
            <span>{selectedHover.title}</span>
          </div>
          <div className="rp-story-pop-body">{selectedHover.body}</div>
          {selectedHover.rule && (
            <div className="rp-story-pop-rule">{selectedHover.rule}</div>
          )}
        </div>
      )}

      {/* Subtle Caption Footnote */}
      <p className="rp-story-foot">
        One execution, fully observable: connect model providers and workflows, enforce 7 sequential safeguards, stream deterministic trace waterfalls, and evaluate results under human ground truth.
      </p>
    </div>
  )
}

/** The landing section: heading, then the comprehensive execution story. */
export const BenchmarkFlowSection: React.FC = () => {
  const c = LANDING_CONTENT.stackFlow
  return (
    <section className="rp-section rp-sf" id="stack" aria-labelledby="rp-sf-title">
      <div className="rp-sf-head">
        <Reveal>
          <p className="rp-eyebrow">Execution Story</p>
          <h2 id="rp-sf-title" className="rp-h2 rp-fade-heading">
            One execution.
            <br />
            Fully observable.
          </h2>
        </Reveal>
        <Reveal delay={0.08}>
          <p className="rp-body">
            Connect any model provider, local server, or workflow. Runport enforces 7 sequential safeguards, captures canonical execution traces, and evaluates performance under strict ground-truth rigor.
          </p>
        </Reveal>
        <Reveal delay={0.14}>
          <a
            className="rp-pill rp-pill-sm rp-pill-glass rp-sf-cta"
            href={c.ctaHref}
            target="_blank"
            rel="noopener noreferrer"
          >
            {c.cta} <span aria-hidden="true">↗</span>
          </a>
        </Reveal>
      </div>
      <BenchmarkFlow />
    </section>
  )
}
