import React, { useState, useEffect, useMemo } from 'react'
import {
  Activity,
  Layers,
  ChevronRight,
  ChevronDown,
  Search,
  CheckCircle2,
  XCircle,
  Clock,
  Coins,
  Cpu,
  Wrench,
  SearchCode,
  GitBranch,
  Bot,
  AlertTriangle,
  Info,
  Filter,
} from 'lucide-react'

export interface SpanData {
  trace_id: string
  span_id: string
  parent_span_id: string | null
  name: string
  kind: 'llm' | 'tool' | 'retrieval' | 'workflow_step' | 'agent' | 'handoff' | 'rerank' | 'router' | 'other'
  status: 'ok' | 'error' | 'timeout' | 'cancelled' | 'unset'
  start_time: string | null
  end_time: string | null
  duration_ms: number | null
  provider: string | null
  model: string | null
  prompt_tokens: number | null
  completion_tokens: number | null
  total_tokens: number | null
  cost_usd: string | null
  cost_basis: string | null
  attributes: Record<string, any>
  events: Array<{ name: string; timestamp: string; attributes: Record<string, any> }>
  error: string | null
  attempt: number
  source: string
  created_at: string
}

export interface TraceData {
  trace_id: string
  run_id: string | null
  case_id: string | null
  target_id: string | null
  session_id: string | null
  name: string
  status: 'ok' | 'error' | 'timeout' | 'cancelled' | 'unset'
  start_time: string | null
  end_time: string | null
  attributes: Record<string, any>
  schema_version: number
  spans: SpanData[]
  source: string
  source_ref: string | null
  created_at: string
}

interface TraceViewProps {
  initialRunId?: string
  initialTraceId?: string
  runsList?: Array<{ run_id: string; model_id: string; total_cases: number; timestamp: string }>
}

const KIND_COLORS: Record<string, { bg: string; text: string; border: string; icon: any }> = {
  llm: { bg: 'rgba(129, 140, 248, 0.15)', text: '#818cf8', border: 'rgba(129, 140, 248, 0.4)', icon: Cpu },
  tool: { bg: 'rgba(251, 191, 36, 0.15)', text: '#fbbf24', border: 'rgba(251, 191, 36, 0.4)', icon: Wrench },
  retrieval: { bg: 'rgba(192, 132, 252, 0.15)', text: '#c084fc', border: 'rgba(192, 132, 252, 0.4)', icon: SearchCode },
  workflow_step: { bg: 'rgba(56, 189, 248, 0.15)', text: '#38bdf8', border: 'rgba(56, 189, 248, 0.4)', icon: GitBranch },
  agent: { bg: 'rgba(52, 211, 153, 0.15)', text: '#34d399', border: 'rgba(52, 211, 153, 0.4)', icon: Bot },
  other: { bg: 'rgba(161, 161, 170, 0.15)', text: '#a1a1aa', border: 'rgba(161, 161, 170, 0.4)', icon: Layers },
}

export default function TraceView({ initialRunId, initialTraceId, runsList = [] }: TraceViewProps) {
  const [selectedRunId, setSelectedRunId] = useState<string>(initialRunId || '')
  const [traces, setTraces] = useState<TraceData[]>([])
  const [selectedTraceId, setSelectedTraceId] = useState<string>(initialTraceId || '')
  const [activeSpanId, setActiveSpanId] = useState<string | null>(null)
  const [loading, setLoading] = useState<boolean>(false)
  const [searchFilter, setSearchFilter] = useState<string>('')
  const [kindFilter, setKindFilter] = useState<string>('all')
  const [errorsOnly, setErrorsOnly] = useState<boolean>(false)
  const [collapsedSpans, setCollapsedSpans] = useState<Record<string, boolean>>({})

  // Update selected run if initial prop changes
  useEffect(() => {
    if (initialRunId) setSelectedRunId(initialRunId)
  }, [initialRunId])

  useEffect(() => {
    if (initialTraceId) setSelectedTraceId(initialTraceId)
  }, [initialTraceId])

  // Load runs if none provided
  const [internalRuns, setInternalRuns] = useState<any[]>(runsList)
  useEffect(() => {
    if (runsList.length === 0) {
      fetch('/api/runs')
        .then((r) => r.json())
        .then((data) => {
          if (Array.isArray(data)) {
            setInternalRuns(data)
            if (!selectedRunId && data.length > 0) {
              setSelectedRunId(data[0].run_id)
            }
          }
        })
        .catch(() => {})
    } else {
      setInternalRuns(runsList)
      if (!selectedRunId && runsList.length > 0) {
        setSelectedRunId(runsList[0].run_id)
      }
    }
  }, [runsList])

  // Fetch traces when run changes
  useEffect(() => {
    if (!selectedRunId) return
    setLoading(true)
    fetch(`/api/runs/${encodeURIComponent(selectedRunId)}/traces`)
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setTraces(data)
          if (data.length > 0) {
            const hasInitial = initialTraceId && data.some((t: TraceData) => t.trace_id === initialTraceId)
            const targetId = hasInitial ? initialTraceId! : data[0].trace_id
            setSelectedTraceId(targetId)
          } else {
            setSelectedTraceId('')
          }
        }
      })
      .catch(() => {
        setTraces([])
      })
      .finally(() => setLoading(false))
  }, [selectedRunId])

  // Currently selected trace object
  const currentTrace = useMemo(() => {
    return traces.find((t) => t.trace_id === selectedTraceId) || null
  }, [traces, selectedTraceId])

  // Compute timing bounds for the waterfall
  const { minTime, maxTime, totalDurationMs } = useMemo(() => {
    if (!currentTrace || !currentTrace.spans.length) {
      return { minTime: 0, maxTime: 100, totalDurationMs: 100 }
    }

    let min = Infinity
    let max = -Infinity

    currentTrace.spans.forEach((s) => {
      if (s.start_time) {
        const t = new Date(s.start_time).getTime()
        if (t < min) min = t
      }
      if (s.end_time) {
        const t = new Date(s.end_time).getTime()
        if (t > max) max = t
      }
    })

    if (min === Infinity || max === -Infinity) {
      // Fallback if timestamps are missing
      const dur = currentTrace.spans.reduce((acc, s) => acc + (s.duration_ms || 0), 0)
      return { minTime: 0, maxTime: Math.max(100, dur), totalDurationMs: Math.max(100, dur) }
    }

    const dur = Math.max(50, max - min)
    return { minTime: min, maxTime: max, totalDurationMs: dur }
  }, [currentTrace])

  // Hierarchy tree organization
  const { visibleSpans, spanMap } = useMemo(() => {
    if (!currentTrace) return { visibleSpans: [], spanMap: new Map() }

    const map = new Map<string, SpanData>()
    const childrenMap = new Map<string | null, SpanData[]>()

    currentTrace.spans.forEach((s) => {
      map.set(s.span_id, s)
      const p = s.parent_span_id || null
      if (!childrenMap.has(p)) childrenMap.set(p, [])
      childrenMap.get(p)!.push(s)
    })

    const result: Array<{ span: SpanData; depth: number; hasChildren: boolean }> = []

    const traverse = (parentId: string | null, depth: number) => {
      const children = childrenMap.get(parentId) || []
      children.forEach((s) => {
        const hasKids = (childrenMap.get(s.span_id) || []).length > 0
        result.push({ span: s, depth, hasChildren: hasKids })
        if (!collapsedSpans[s.span_id]) {
          traverse(s.span_id, depth + 1)
        }
      })
    }

    traverse(null, 0)
    return { visibleSpans: result, spanMap: map }
  }, [currentTrace, collapsedSpans])

  // Filtered list of visible spans
  const filteredVisibleSpans = useMemo(() => {
    return visibleSpans.filter(({ span }) => {
      if (kindFilter !== 'all' && span.kind !== kindFilter) return false
      if (errorsOnly && span.status === 'ok') return false
      if (searchFilter.trim()) {
        const q = searchFilter.toLowerCase()
        const matchName = span.name.toLowerCase().includes(q)
        const matchId = span.span_id.toLowerCase().includes(q)
        const matchErr = span.error ? span.error.toLowerCase().includes(q) : false
        if (!matchName && !matchId && !matchErr) return false
      }
      return true
    })
  }, [visibleSpans, kindFilter, errorsOnly, searchFilter])

  // Active span object for details drawer
  const activeSpan = useMemo(() => {
    if (!activeSpanId || !spanMap) return null
    return spanMap.get(activeSpanId) || null
  }, [activeSpanId, spanMap])

  // Toggle span fold/unfold
  const toggleCollapse = (spanId: string) => {
    setCollapsedSpans((prev) => ({ ...prev, [spanId]: !prev[spanId] }))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Top Header Card */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <div className="card-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <Activity size={18} color="var(--accent-blue)" />
              Trace Waterfall & Trajectory Explorer
            </div>
            <div className="card-subtitle">
              Inspect multi-step agent trajectories, tool invocations, and hierarchical span trees.
            </div>
          </div>

          {/* Select Run */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <label className="form-label" style={{ margin: 0 }}>Evaluation Run:</label>
            <select
              className="select"
              style={{ maxWidth: 320 }}
              value={selectedRunId}
              onChange={(e) => setSelectedRunId(e.target.value)}
            >
              {internalRuns.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {r.run_id} ({r.model_id} - {r.total_cases} cases)
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Traces Pill Bar */}
        <div style={{ marginTop: '1rem', borderTop: '1px solid var(--border-color)', paddingTop: '0.85rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
            <Layers size={14} color="var(--text-secondary)" />
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
              Evaluation Cases ({traces.length})
            </span>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', overflowX: 'auto', paddingBottom: '0.5rem' }}>
            {traces.length === 0 && !loading && (
              <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                No canonical traces recorded for this run.
              </div>
            )}
            {traces.map((t) => {
              const isSelected = t.trace_id === selectedTraceId
              const isOk = t.status === 'ok'
              const isErr = t.status === 'error'
              return (
                <button
                  key={t.trace_id}
                  onClick={() => {
                    setSelectedTraceId(t.trace_id)
                    setActiveSpanId(null)
                  }}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '0.4rem',
                    padding: '0.35rem 0.65rem',
                    borderRadius: 6,
                    border: `1px solid ${isSelected ? 'var(--accent-blue)' : 'var(--border-color)'}`,
                    background: isSelected ? 'var(--accent-soft)' : 'var(--bg-input)',
                    color: isSelected ? 'var(--text-primary)' : 'var(--text-secondary)',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {isOk ? <CheckCircle2 size={12} color="var(--accent-green)" /> : isErr ? <XCircle size={12} color="var(--accent-red)" /> : <Clock size={12} color="var(--accent-amber)" />}
                  <span style={{ fontWeight: 600 }}>{t.case_id || t.name}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: '0.7rem' }}>({t.spans.length} spans)</span>
                </button>
              )
            })}
          </div>
        </div>
      </div>

      {/* Selected Trace Header & Waterfall View */}
      {currentTrace && (
        <div className="card">
          {/* Trace Summary Bar */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem', paddingBottom: '1rem', borderBottom: '1px solid var(--border-color)' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-primary)' }}>{currentTrace.name}</span>
                <span
                  style={{
                    fontSize: '0.7rem',
                    padding: '0.15rem 0.45rem',
                    borderRadius: 4,
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    background: currentTrace.status === 'ok' ? 'rgba(74, 222, 128, 0.15)' : 'rgba(248, 113, 113, 0.15)',
                    color: currentTrace.status === 'ok' ? 'var(--accent-green)' : 'var(--accent-red)',
                    border: `1px solid ${currentTrace.status === 'ok' ? 'rgba(74, 222, 128, 0.3)' : 'rgba(248, 113, 113, 0.3)'}`,
                  }}
                >
                  {currentTrace.status}
                </span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                  {currentTrace.trace_id}
                </span>
              </div>
              <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                Target: <strong>{currentTrace.target_id || '—'}</strong> • Case: <strong>{currentTrace.case_id || '—'}</strong> • Spans: <strong>{currentTrace.spans.length}</strong>
              </div>
            </div>

            {/* Filter Toolbar */}
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
              <div style={{ position: 'relative' }}>
                <Search size={14} style={{ position: 'absolute', left: 8, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  placeholder="Filter spans..."
                  className="input"
                  style={{ paddingLeft: '1.75rem', height: 32, fontSize: '0.75rem', width: 140 }}
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                />
              </div>

              <select
                className="select"
                style={{ height: 32, fontSize: '0.75rem', width: 110 }}
                value={kindFilter}
                onChange={(e) => setKindFilter(e.target.value)}
              >
                <option value="all">All Kinds</option>
                <option value="llm">LLM</option>
                <option value="tool">Tool</option>
                <option value="retrieval">Retrieval</option>
                <option value="workflow_step">Step</option>
                <option value="agent">Agent</option>
              </select>

              <button
                onClick={() => setErrorsOnly((prev) => !prev)}
                style={{
                  height: 32,
                  padding: '0 0.5rem',
                  borderRadius: 6,
                  border: `1px solid ${errorsOnly ? 'var(--accent-red)' : 'var(--border-color)'}`,
                  background: errorsOnly ? 'rgba(248, 113, 113, 0.15)' : 'var(--bg-input)',
                  color: errorsOnly ? 'var(--accent-red)' : 'var(--text-secondary)',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.3rem',
                }}
              >
                <AlertTriangle size={12} />
                Errors
              </button>
            </div>
          </div>

          {/* Waterfall Timeline & Span Tree */}
          <div style={{ marginTop: '1rem' }}>
            {/* Header Timeline Axis */}
            <div style={{ display: 'grid', gridTemplateColumns: '340px 1fr', paddingBottom: '0.4rem', borderBottom: '1px solid var(--border-color)' }}>
              <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                Operation & Hierarchy
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-muted)', paddingLeft: '0.5rem' }}>
                <span>0 ms</span>
                <span>{(totalDurationMs * 0.25).toFixed(0)} ms</span>
                <span>{(totalDurationMs * 0.5).toFixed(0)} ms</span>
                <span>{(totalDurationMs * 0.75).toFixed(0)} ms</span>
                <span>{totalDurationMs.toFixed(0)} ms</span>
              </div>
            </div>

            {/* Span Rows */}
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {filteredVisibleSpans.length === 0 && (
                <div style={{ padding: '1.5rem', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem' }}>
                  No spans match the selected filters.
                </div>
              )}

              {filteredVisibleSpans.map(({ span, depth, hasChildren }) => {
                const kindMeta = KIND_COLORS[span.kind] || KIND_COLORS.other
                const KindIcon = kindMeta.icon
                const isSelected = activeSpanId === span.span_id
                const isErr = span.status === 'error'
                const isTimeout = span.status === 'timeout'

                // Waterfall bar geometry calculation
                let leftPct = 0
                let widthPct = 100
                if (span.start_time && minTime !== Infinity) {
                  const sTime = new Date(span.start_time).getTime()
                  leftPct = Math.max(0, Math.min(99, ((sTime - minTime) / totalDurationMs) * 100))
                }
                if (span.duration_ms != null && totalDurationMs > 0) {
                  widthPct = Math.max(1.5, Math.min(100 - leftPct, (span.duration_ms / totalDurationMs) * 100))
                }

                return (
                  <div
                    key={span.span_id}
                    onClick={() => setActiveSpanId(span.span_id)}
                    style={{
                      display: 'grid',
                      gridTemplateColumns: '340px 1fr',
                      alignItems: 'center',
                      padding: '0.4rem 0',
                      borderBottom: '1px solid var(--border-color)',
                      background: isSelected ? 'var(--accent-soft)' : 'transparent',
                      cursor: 'pointer',
                      transition: 'background 0.1s ease',
                    }}
                  >
                    {/* Left: Tree indentation + Kind + Name */}
                    <div style={{ display: 'flex', alignItems: 'center', paddingLeft: `${depth * 18}px`, overflow: 'hidden' }}>
                      {hasChildren ? (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            toggleCollapse(span.span_id)
                          }}
                          style={{
                            background: 'none',
                            border: 'none',
                            cursor: 'pointer',
                            padding: 0,
                            marginRight: '0.3rem',
                            color: 'var(--text-muted)',
                            display: 'flex',
                            alignItems: 'center',
                          }}
                        >
                          {collapsedSpans[span.span_id] ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                        </button>
                      ) : (
                        <span style={{ width: 14, marginRight: '0.3rem', display: 'inline-block' }} />
                      )}

                      <span
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.25rem',
                          fontSize: '0.65rem',
                          fontWeight: 700,
                          padding: '0.1rem 0.35rem',
                          borderRadius: 4,
                          background: kindMeta.bg,
                          color: kindMeta.text,
                          border: `1px solid ${kindMeta.border}`,
                          marginRight: '0.45rem',
                          textTransform: 'uppercase',
                        }}
                      >
                        <KindIcon size={10} />
                        {span.kind}
                      </span>

                      <span
                        style={{
                          fontSize: '0.775rem',
                          fontWeight: 600,
                          color: isErr ? 'var(--accent-red)' : 'var(--text-primary)',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }}
                        title={span.name}
                      >
                        {span.name}
                      </span>
                    </div>

                    {/* Right: Gantt Waterfall Bar + Metrics */}
                    <div style={{ position: 'relative', height: 22, display: 'flex', alignItems: 'center', paddingLeft: '0.5rem' }}>
                      {/* Grid background guide lines */}
                      <div style={{ position: 'absolute', inset: 0, display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', pointerEvents: 'none' }}>
                        <div style={{ borderRight: '1px dashed rgba(255, 255, 255, 0.05)' }} />
                        <div style={{ borderRight: '1px dashed rgba(255, 255, 255, 0.05)' }} />
                        <div style={{ borderRight: '1px dashed rgba(255, 255, 255, 0.05)' }} />
                      </div>

                      {/* Visual Waterfall Bar */}
                      <div
                        style={{
                          position: 'absolute',
                          left: `${leftPct}%`,
                          width: `${widthPct}%`,
                          height: 14,
                          borderRadius: 3,
                          background: isErr ? 'var(--accent-red)' : isTimeout ? 'var(--accent-amber)' : kindMeta.text,
                          opacity: isSelected ? 1 : 0.85,
                          boxShadow: isSelected ? '0 0 8px rgba(129, 140, 248, 0.5)' : 'none',
                          transition: 'all 0.15s ease',
                        }}
                      />

                      {/* Telemetry pill beside bar */}
                      <div
                        style={{
                          position: 'relative',
                          zIndex: 1,
                          fontSize: '0.7rem',
                          fontFamily: 'var(--font-mono)',
                          color: 'var(--text-secondary)',
                          marginLeft: `calc(${leftPct + widthPct}% + 8px)`,
                          whiteSpace: 'nowrap',
                        }}
                      >
                        {span.duration_ms != null ? `${span.duration_ms.toFixed(1)}ms` : '—'}
                        {span.total_tokens != null && ` • ${span.total_tokens}t`}
                        {span.cost_usd != null && ` • $${span.cost_usd}`}
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Span Detail Drawer / Inspector */}
          {activeSpan && (
            <div
              style={{
                marginTop: '1.5rem',
                padding: '1rem',
                borderRadius: 8,
                border: '1px solid var(--border-color)',
                background: 'var(--bg-input)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Info size={16} color="var(--accent-blue)" />
                  <span style={{ fontSize: '0.85rem', fontWeight: 700, color: 'var(--text-primary)' }}>
                    Span Inspector: {activeSpan.name}
                  </span>
                  <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    ({activeSpan.span_id})
                  </span>
                </div>
                <button
                  onClick={() => setActiveSpanId(null)}
                  style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '0.75rem' }}
                >
                  ✕ Close
                </button>
              </div>

              {/* Inspector Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Kind</div>
                  <div style={{ fontWeight: 600, fontSize: '0.8rem', textTransform: 'uppercase', color: KIND_COLORS[activeSpan.kind]?.text }}>
                    {activeSpan.kind}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Status</div>
                  <div style={{ fontWeight: 600, fontSize: '0.8rem', color: activeSpan.status === 'ok' ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                    {activeSpan.status.toUpperCase()}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Duration</div>
                  <div style={{ fontWeight: 600, fontSize: '0.8rem' }}>
                    {activeSpan.duration_ms != null ? `${activeSpan.duration_ms.toFixed(2)} ms` : '—'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Tokens (In / Out / Total)</div>
                  <div style={{ fontWeight: 600, fontSize: '0.8rem' }}>
                    {activeSpan.prompt_tokens ?? '—'} / {activeSpan.completion_tokens ?? '—'} / {activeSpan.total_tokens ?? '—'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Cost USD & Basis</div>
                  <div style={{ fontWeight: 600, fontSize: '0.8rem' }}>
                    {activeSpan.cost_usd ? `$${activeSpan.cost_usd}` : '—'} ({activeSpan.cost_basis || 'UNAVAILABLE'})
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Parent Span ID</div>
                  <div style={{ fontWeight: 600, fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                    {activeSpan.parent_span_id || 'None (Root)'}
                  </div>
                </div>
              </div>

              {/* Error display if failed */}
              {activeSpan.error && (
                <div style={{ marginBottom: '1rem', padding: '0.5rem 0.75rem', borderRadius: 6, background: 'rgba(248, 113, 113, 0.15)', border: '1px solid rgba(248, 113, 113, 0.3)', color: 'var(--accent-red)', fontSize: '0.75rem' }}>
                  <strong>Error details:</strong> {activeSpan.error}
                </div>
              )}

              {/* Structured Attributes JSON */}
              {activeSpan.attributes && Object.keys(activeSpan.attributes).length > 0 && (
                <div>
                  <div style={{ fontSize: '0.7rem', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', marginBottom: '0.3rem' }}>
                    Structured Attributes
                  </div>
                  <pre
                    style={{
                      margin: 0,
                      padding: '0.75rem',
                      borderRadius: 6,
                      background: 'var(--bg-app)',
                      border: '1px solid var(--border-color)',
                      fontSize: '0.725rem',
                      fontFamily: 'var(--font-mono)',
                      color: 'var(--text-primary)',
                      overflowX: 'auto',
                      maxHeight: 200,
                    }}
                  >
                    {JSON.stringify(activeSpan.attributes, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
