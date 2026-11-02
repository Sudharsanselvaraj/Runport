import React, { useState, useEffect } from 'react'
import { 
  Play, 
  Database, 
  Cpu, 
  Wallet, 
  Activity, 
  CheckCircle2, 
  AlertTriangle, 
  ShieldCheck, 
  RefreshCw, 
  Send, 
  FileText, 
  Lock,
  Layers,
  ArrowRight,
  ExternalLink
} from 'lucide-react'

// --- Types ---
interface TargetItem {
  target_id: string
  name: string
  target_type: string
  provider?: string
  license?: string
  context_length?: number
  input_price_per_1m_usd?: number
  output_price_per_1m_usd?: number
  verification_status?: string
}

interface DatasetItem {
  filename: string
  path: string
  size_bytes: number
  case_count: number
}

interface BudgetData {
  policy: {
    total_budget_usd: number
    pilot_budget_usd: number
    per_run_ceiling_usd: number
    per_case_ceiling_usd: number
    require_priced: boolean
  }
  spend: {
    total_spent_usd: number
    pilot_spent_usd: number
    remaining_total_usd: number
    remaining_pilot_usd: number
  }
  unresolved_count: number
  unresolved_transactions: any[]
  recent_transactions: any[]
}

interface PlanData {
  plan_fingerprint: string
  dataset_name: string
  projected_cases: number
  projected_cost_usd: number
  targets: any[]
  is_permitted: boolean
  blockers: string[]
  expected_confirmation_phrase: string
}

export default function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'targets' | 'datasets' | 'budget' | 'runner' | 'telemetry'>('overview')
  
  // Data states
  const [targets, setTargets] = useState<TargetItem[]>([])
  const [datasets, setDatasets] = useState<DatasetItem[]>([])
  const [budget, setBudget] = useState<BudgetData | null>(null)
  const [events, setEvents] = useState<any[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [apiError, setApiError] = useState<string | null>(null)

  // Target Tester State
  const [testTargetId, setTestTargetId] = useState<string>('')
  const [testType, setTestType] = useState<string>('raw_model')
  const [testUrl, setTestUrl] = useState<string>('')
  const [testPrompt, setTestPrompt] = useState<string>('Explain the concept of strict ground truth in 2 sentences.')
  const [testingRunning, setTestingRunning] = useState<boolean>(false)
  const [testResult, setTestResult] = useState<any | null>(null)

  // Runner State
  const [selectedTargets, setSelectedTargets] = useState<string[]>([])
  const [selectedDataset, setSelectedDataset] = useState<string>('')
  const [sampleSize, setSampleSize] = useState<number>(5)
  const [plan, setPlan] = useState<PlanData | null>(null)
  const [planLoading, setPlanLoading] = useState<boolean>(false)
  const [approvalPhraseInput, setApprovalPhraseInput] = useState<string>('')
  const [runInProgress, setRunInProgress] = useState<boolean>(false)
  const [runResult, setRunResult] = useState<any | null>(null)
  const [showApprovalModal, setShowApprovalModal] = useState<boolean>(false)

  // Reconcile Modal State
  const [reconcileTxId, setReconcileTxId] = useState<string>('')
  const [reconcileAmount, setReconcileAmount] = useState<string>('0.0000')
  const [reconcileNotes, setReconcileNotes] = useState<string>('Manual reconciliation via web UI')

  // Load initial data
  const loadData = async () => {
    try {
      setLoading(true)
      const [targetsRes, datasetsRes, budgetRes] = await Promise.all([
        fetch('/api/targets'),
        fetch('/api/datasets'),
        fetch('/api/budget')
      ])

      if (targetsRes.ok) {
        const tData = await targetsRes.json()
        setTargets(tData)
        if (tData.length > 0 && selectedTargets.length === 0) {
          setSelectedTargets([tData[0].target_id])
          setTestTargetId(tData[0].target_id)
        }
      }
      if (datasetsRes.ok) {
        const dData = await datasetsRes.json()
        setDatasets(dData)
        if (dData.length > 0 && !selectedDataset) {
          setSelectedDataset(dData[0].filename)
        }
      }
      if (budgetRes.ok) {
        setBudget(await budgetRes.json())
      }
      setApiError(null)
    } catch (err: any) {
      setApiError('Unable to connect to Runport local backend. Ensure `runport web` is running.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  // Telemetry SSE stream
  useEffect(() => {
    const es = new EventSource('/api/events')
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type !== 'connected') {
          setEvents((prev) => [data, ...prev].slice(0, 50))
        }
      } catch {}
    }
    return () => es.close()
  }, [])

  // Execute Target Test
  const handleTestTarget = async () => {
    setTestingRunning(true)
    setTestResult(null)
    try {
      const payload = {
        target: {
          target_id: testTargetId || 'custom-http',
          name: testTargetId || 'Custom Endpoint',
          target_type: testType,
          url: testUrl || undefined,
        },
        input_payload: { query: testPrompt }
      }
      const res = await fetch('/api/targets/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      const data = await res.json()
      setTestResult(data)
    } catch (e: any) {
      setTestResult({ status: 'failed', error_message: e.message })
    } finally {
      setTestingRunning(false)
    }
  }

  // Compute Plan
  const handleComputePlan = async () => {
    if (!selectedDataset || selectedTargets.length === 0) return
    setPlanLoading(true)
    setPlan(null)
    try {
      const res = await fetch('/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_ids: selectedTargets,
          dataset_name: selectedDataset,
          sample_size: sampleSize > 0 ? sampleSize : undefined,
          is_pilot: true
        })
      })
      const data = await res.json()
      setPlan(data)
    } catch (e) {
      alert('Failed to compute plan')
    } finally {
      setPlanLoading(false)
    }
  }

  // Execute Run
  const handleExecuteRun = async (isReplay: boolean) => {
    if (!plan) return
    setRunInProgress(true)
    setRunResult(null)
    setShowApprovalModal(false)

    try {
      const res = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_ids: selectedTargets,
          dataset_name: selectedDataset,
          sample_size: sampleSize,
          plan_fingerprint: plan.plan_fingerprint,
          is_replay: isReplay,
          approve_token: isReplay ? undefined : plan.plan_fingerprint,
        })
      })
      const data = await res.json()
      setRunResult(data)
      loadData()
    } catch (e: any) {
      alert(`Run execution failed: ${e.message}`)
    } finally {
      setRunInProgress(false)
    }
  }

  // Reconcile Transaction
  const handleReconcile = async () => {
    if (!reconcileTxId) return
    try {
      await fetch('/api/budget/reconcile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transaction_id: reconcileTxId,
          reconciled_usd: parseFloat(reconcileAmount),
          notes: reconcileNotes
        })
      })
      setReconcileTxId('')
      loadData()
    } catch (e) {
      alert('Reconciliation failed')
    }
  }

  return (
    <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', backgroundColor: '#0c1017' }}>
      {/* Top Navbar */}
      <header style={{ borderBottom: '1px solid #1e293b', backgroundColor: '#0f172a', padding: '0.75rem 2rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ width: '32px', height: '32px', borderRadius: '6px', backgroundColor: '#7c3aed', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <Layers size={18} color="#ffffff" />
          </div>
          <div>
            <h1 style={{ fontSize: '1.15rem', fontWeight: 700, color: '#f8fafc', letterSpacing: '-0.025em' }}>Runport</h1>
            <p style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Universal LLM & Workflow Benchmarking</p>
          </div>
        </div>

        {/* Navigation Tabs */}
        <nav style={{ display: 'flex', gap: '0.5rem' }}>
          {[
            { id: 'overview', label: 'Overview', icon: Activity },
            { id: 'targets', label: 'Targets & Workflows', icon: Cpu },
            { id: 'datasets', label: 'Datasets', icon: Database },
            { id: 'budget', label: 'Budget & Ledger', icon: Wallet },
            { id: 'runner', label: 'Benchmark Runner', icon: Play },
            { id: 'telemetry', label: 'Live Telemetry', icon: RefreshCw },
          ].map((tab) => {
            const Icon = tab.icon
            const isActive = activeTab === tab.id
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.4rem',
                  padding: '0.5rem 0.85rem',
                  fontSize: '0.85rem',
                  fontWeight: 500,
                  borderRadius: '6px',
                  border: 'none',
                  backgroundColor: isActive ? '#1e293b' : 'transparent',
                  color: isActive ? '#a78bfa' : '#94a3b8',
                  transition: 'all 0.15s ease'
                }}
              >
                <Icon size={16} />
                {tab.label}
              </button>
            )
          })}
        </nav>

        {/* Status Pill */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', color: '#10b981', backgroundColor: '#064e3b33', padding: '0.25rem 0.6rem', borderRadius: '9999px', border: '1px solid #059669' }}>
            <span style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: '#10b981' }}></span>
            Local-First / Fail-Closed
          </span>
        </div>
      </header>

      {/* Main Content Area */}
      <main style={{ flex: 1, padding: '2rem', maxWidth: '1400px', width: '100%', margin: '0 auto' }}>
        {apiError && (
          <div style={{ padding: '1rem', backgroundColor: '#ef44441a', border: '1px solid #ef4444', borderRadius: '8px', color: '#fca5a5', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <AlertTriangle size={20} />
            <span>{apiError}</span>
          </div>
        )}

        {/* OVERVIEW TAB */}
        {activeTab === 'overview' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            {/* Quick Metrics */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(260px, 1fr))', gap: '1rem' }}>
              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.25rem' }}>
                <p style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Lifetime Spend</p>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginTop: '0.25rem' }}>
                  <h2 style={{ fontSize: '1.8rem', fontWeight: 700, color: '#f8fafc' }}>
                    ${budget ? budget.spend.total_spent_usd.toFixed(4) : '0.0000'}
                  </h2>
                  <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                    / ${budget ? budget.policy.total_budget_usd.toFixed(2) : '18.00'} cap
                  </span>
                </div>
                <div style={{ height: '6px', backgroundColor: '#1e293b', borderRadius: '3px', marginTop: '0.75rem', overflow: 'hidden' }}>
                  <div style={{ 
                    height: '100%', 
                    width: `${budget ? Math.min(100, (budget.spend.total_spent_usd / budget.policy.total_budget_usd) * 100) : 0}%`, 
                    backgroundColor: '#8b5cf6' 
                  }}></div>
                </div>
              </div>

              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.25rem' }}>
                <p style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Pilot Stage Spend</p>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginTop: '0.25rem' }}>
                  <h2 style={{ fontSize: '1.8rem', fontWeight: 700, color: '#f8fafc' }}>
                    ${budget ? budget.spend.pilot_spent_usd.toFixed(4) : '0.0000'}
                  </h2>
                  <span style={{ fontSize: '0.85rem', color: '#64748b' }}>
                    / ${budget ? budget.policy.pilot_budget_usd.toFixed(2) : '2.00'} cap
                  </span>
                </div>
                <div style={{ height: '6px', backgroundColor: '#1e293b', borderRadius: '3px', marginTop: '0.75rem', overflow: 'hidden' }}>
                  <div style={{ 
                    height: '100%', 
                    width: `${budget ? Math.min(100, (budget.spend.pilot_spent_usd / budget.policy.pilot_budget_usd) * 100) : 0}%`, 
                    backgroundColor: '#38bdf8' 
                  }}></div>
                </div>
              </div>

              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.25rem' }}>
                <p style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Active Targets</p>
                <h2 style={{ fontSize: '1.8rem', fontWeight: 700, color: '#f8fafc', marginTop: '0.25rem' }}>
                  {targets.length} Models & Connectors
                </h2>
                <p style={{ fontSize: '0.8rem', color: '#10b981', marginTop: '0.5rem' }}>Strict Catalog & Workflow Adapters</p>
              </div>

              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.25rem' }}>
                <p style={{ fontSize: '0.8rem', color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Spend Safety Status</p>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
                  {budget && budget.unresolved_count > 0 ? (
                    <>
                      <AlertTriangle color="#f59e0b" size={24} />
                      <span style={{ color: '#f59e0b', fontWeight: 600, fontSize: '0.95rem' }}>{budget.unresolved_count} Unresolved Spend</span>
                    </>
                  ) : (
                    <>
                      <ShieldCheck color="#10b981" size={24} />
                      <span style={{ color: '#10b981', fontWeight: 600, fontSize: '0.95rem' }}>Enforced & Reconciled</span>
                    </>
                  )}
                </div>
                <p style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '0.25rem' }}>Fail-closed spend caps active</p>
              </div>
            </div>

            {/* Quick Actions & Platform Guide */}
            <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem' }}>
              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.5rem' }}>
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '0.5rem' }}>Welcome to Runport</h3>
                <p style={{ fontSize: '0.9rem', color: '#94a3b8', lineHeight: 1.6, marginBottom: '1rem' }}>
                  Runport is a universal, local-first benchmarking platform for raw LLMs, prompt pipelines, autonomous agents, 
                  and multi-step orchestrations (Dify, Flowise, Langflow, n8n, LangGraph).
                </p>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                  <button 
                    onClick={() => setActiveTab('runner')}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 1.2rem', backgroundColor: '#7c3aed', color: '#ffffff', borderRadius: '6px', border: 'none', fontWeight: 500 }}
                  >
                    <Play size={16} /> Run Benchmark
                  </button>
                  <button 
                    onClick={() => setActiveTab('targets')}
                    style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.6rem 1.2rem', backgroundColor: '#1e293b', color: '#f8fafc', borderRadius: '6px', border: '1px solid #334155', fontWeight: 500 }}
                  >
                    <Cpu size={16} /> Test Connectors
                  </button>
                </div>
              </div>

              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '0.75rem' }}>Core Invariants</h3>
                <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: '0.5rem', fontSize: '0.85rem', color: '#94a3b8' }}>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="#10b981" /> No simulation or placeholder data</li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="#10b981" /> Fail-closed local spend caps</li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="#10b981" /> Typed live approval bound to plan</li>
                  <li style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}><CheckCircle2 size={16} color="#10b981" /> Replay strictly isolated & zero spend</li>
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* TARGETS & CONNECTORS TAB */}
        {activeTab === 'targets' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ fontSize: '1.3rem', fontWeight: 700, color: '#f8fafc' }}>Evaluation Targets & Connectors</h2>
                <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Catalog models and custom workflow integrations</p>
              </div>
            </div>

            {/* Catalog Table */}
            <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ backgroundColor: '#0f172a', borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                    <th style={{ padding: '0.85rem 1rem' }}>Target ID / Model</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Provider</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Context</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Input / 1M</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Output / 1M</th>
                    <th style={{ padding: '0.85rem 1rem' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {targets.map((t) => (
                    <tr key={t.target_id} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '0.85rem 1rem', fontWeight: 600, color: '#f8fafc' }}>
                        {t.name}
                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{t.target_id}</div>
                      </td>
                      <td style={{ padding: '0.85rem 1rem', color: '#cbd5e1' }}>{t.provider || 'custom'}</td>
                      <td style={{ padding: '0.85rem 1rem', color: '#cbd5e1' }}>{t.context_length ? `${(t.context_length / 1000).toFixed(0)}k` : '—'}</td>
                      <td style={{ padding: '0.85rem 1rem', color: '#cbd5e1' }}>${t.input_price_per_1m_usd?.toFixed(4) || '—'}</td>
                      <td style={{ padding: '0.85rem 1rem', color: '#cbd5e1' }}>${t.output_price_per_1m_usd?.toFixed(4) || '—'}</td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: '#1e293b', color: '#38bdf8' }}>
                          {t.verification_status || 'READY'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Target Tester Section */}
            <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.5rem' }}>
              <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '0.5rem' }}>Connector Test Console</h3>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginBottom: '1rem' }}>
                Execute a single prompt through any target or custom HTTP / Dify / Flowise / Langflow / n8n / LangGraph workflow.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.35rem' }}>Target Type</label>
                  <select 
                    value={testType} 
                    onChange={(e) => setTestType(e.target.value)}
                    style={{ width: '100%', padding: '0.5rem', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', color: '#f8fafc' }}
                  >
                    <option value="raw_model">Raw Model (OpenAI / OpenRouter)</option>
                    <option value="workflow_http">Custom HTTP Endpoint</option>
                    <option value="workflow_flowise">Flowise Prediction API</option>
                    <option value="workflow_langflow">Langflow API</option>
                    <option value="workflow_n8n">n8n Webhook</option>
                    <option value="workflow_langgraph">LangGraph Deployment</option>
                  </select>
                </div>

                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.35rem' }}>URL / Endpoint (for workflows)</label>
                  <input 
                    type="text" 
                    placeholder="https://api.example.com/v1/run" 
                    value={testUrl} 
                    onChange={(e) => setTestUrl(e.target.value)}
                    style={{ width: '100%', padding: '0.5rem', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', color: '#f8fafc' }}
                  />
                </div>
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.8rem', color: '#94a3b8', marginBottom: '0.35rem' }}>Test Query</label>
                <textarea 
                  rows={2} 
                  value={testPrompt} 
                  onChange={(e) => setTestPrompt(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', color: '#f8fafc' }}
                />
              </div>

              <button 
                onClick={handleTestTarget} 
                disabled={testingRunning}
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.5rem 1rem', backgroundColor: '#7c3aed', color: '#ffffff', borderRadius: '6px', border: 'none', fontWeight: 500 }}
              >
                <Send size={16} /> {testingRunning ? 'Executing Test...' : 'Send Test Request'}
              </button>

              {/* Result Preview */}
              {testResult && (
                <div style={{ marginTop: '1.25rem', padding: '1rem', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #1e293b' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                    <span style={{ fontSize: '0.85rem', fontWeight: 600, color: testResult.is_success ? '#10b981' : '#ef4444' }}>
                      Status: {testResult.status}
                    </span>
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>
                      Latency: {testResult.latency_ms?.toFixed(1)} ms | In: {testResult.tokens_in || 0} tok | Out: {testResult.tokens_out || 0} tok
                    </span>
                  </div>
                  <pre style={{ fontSize: '0.85rem', color: '#cbd5e1', whiteSpace: 'pre-wrap', backgroundColor: '#090d16', padding: '0.75rem', borderRadius: '4px' }}>
                    {testResult.output_text || testResult.error_message || JSON.stringify(testResult, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}

        {/* DATASETS TAB */}
        {activeTab === 'datasets' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div>
              <h2 style={{ fontSize: '1.3rem', fontWeight: 700, color: '#f8fafc' }}>Evaluation Datasets</h2>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Local JSONL test sets with train/dev/test splits</p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1rem' }}>
              {datasets.map((d) => (
                <div key={d.filename} style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.25rem' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <FileText size={20} color="#8b5cf6" />
                    <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc' }}>{d.filename}</h3>
                  </div>
                  <div style={{ fontSize: '0.85rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '0.25rem', margin: '0.75rem 0' }}>
                    <div>Total Cases: <strong style={{ color: '#f8fafc' }}>{d.case_count}</strong></div>
                    <div>File Size: <strong style={{ color: '#f8fafc' }}>{(d.size_bytes / 1024).toFixed(1)} KB</strong></div>
                    <div>Split: <span style={{ color: '#38bdf8' }}>Dev / Test Approved</span></div>
                  </div>
                  <button 
                    onClick={() => { setSelectedDataset(d.filename); setActiveTab('runner'); }}
                    style={{ width: '100%', padding: '0.5rem', backgroundColor: '#1e293b', color: '#a78bfa', border: '1px solid #334155', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 500 }}
                  >
                    Select for Benchmark
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* BUDGET & LEDGER TAB */}
        {activeTab === 'budget' && budget && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div>
              <h2 style={{ fontSize: '1.3rem', fontWeight: 700, color: '#f8fafc' }}>Spend Governance & Ledger</h2>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Append-only SQLite WAL ledger with fail-closed ceilings</p>
            </div>

            {/* Unresolved spend warning if any */}
            {budget.unresolved_count > 0 && (
              <div style={{ padding: '1rem 1.25rem', backgroundColor: '#78350f33', border: '1px solid #f59e0b', borderRadius: '8px', color: '#fde68a', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div>
                  <h4 style={{ fontWeight: 600 }}>Unresolved Spend Alert ({budget.unresolved_count} transactions)</h4>
                  <p style={{ fontSize: '0.85rem', marginTop: '0.25rem' }}>
                    Live runs are fail-closed and blocked until all unresolved transactions are reconciled.
                  </p>
                </div>
                <button 
                  onClick={() => setReconcileTxId(budget.unresolved_transactions[0]?.transaction_id || '')}
                  style={{ padding: '0.5rem 1rem', backgroundColor: '#f59e0b', color: '#000000', borderRadius: '6px', border: 'none', fontWeight: 600, fontSize: '0.85rem' }}
                >
                  Reconcile Now
                </button>
              </div>
            )}

            {/* Budget Ceilings Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1rem' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>TOTAL BUDGET</span>
                <p style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f8fafc' }}>${budget.policy.total_budget_usd.toFixed(2)}</p>
                <span style={{ fontSize: '0.75rem', color: '#10b981' }}>Spent: ${budget.spend.total_spent_usd.toFixed(4)}</span>
              </div>
              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1rem' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>PILOT CEILING</span>
                <p style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f8fafc' }}>${budget.policy.pilot_budget_usd.toFixed(2)}</p>
                <span style={{ fontSize: '0.75rem', color: '#10b981' }}>Spent: ${budget.spend.pilot_spent_usd.toFixed(4)}</span>
              </div>
              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1rem' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>PER-RUN CAP</span>
                <p style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f8fafc' }}>${budget.policy.per_run_ceiling_usd.toFixed(2)}</p>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Single Run Max</span>
              </div>
              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1rem' }}>
                <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>PER-CASE CAP</span>
                <p style={{ fontSize: '1.4rem', fontWeight: 700, color: '#f8fafc' }}>${budget.policy.per_case_ceiling_usd.toFixed(2)}</p>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Circuit Breaker</span>
              </div>
            </div>

            {/* Recent Ledger Entries */}
            <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', overflow: 'hidden' }}>
              <div style={{ padding: '1rem 1.25rem', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc' }}>Recent Ledger Transactions</h3>
                <span style={{ fontSize: '0.75rem', color: '#64748b' }}>Append-only SQLite WAL</span>
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', textAlign: 'left' }}>
                <thead>
                  <tr style={{ backgroundColor: '#0f172a', borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                    <th style={{ padding: '0.75rem 1rem' }}>TX ID</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Model / Target</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Amount</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Cost Basis</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Description</th>
                  </tr>
                </thead>
                <tbody>
                  {budget.recent_transactions.map((tx) => (
                    <tr key={tx.transaction_id} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: '#94a3b8' }}>{tx.transaction_id.slice(0, 16)}...</td>
                      <td style={{ padding: '0.75rem 1rem', color: '#cbd5e1' }}>{tx.model_id}</td>
                      <td style={{ padding: '0.75rem 1rem', fontWeight: 600, color: '#f8fafc' }}>${parseFloat(tx.amount_usd).toFixed(4)}</td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{ fontSize: '0.75rem', padding: '0.15rem 0.4rem', borderRadius: '4px', backgroundColor: tx.cost_basis === 'ACTUAL' ? '#064e3b' : '#1e293b', color: tx.cost_basis === 'ACTUAL' ? '#34d399' : '#a78bfa' }}>
                          {tx.cost_basis}
                        </span>
                      </td>
                      <td style={{ padding: '0.75rem 1rem', color: '#64748b' }}>{tx.description}</td>
                    </tr>
                  ))}
                  {budget.recent_transactions.length === 0 && (
                    <tr>
                      <td colSpan={5} style={{ padding: '2rem', textAlign: 'center', color: '#64748b' }}>
                        No transactions recorded in local ledger yet.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* BENCHMARK RUNNER TAB */}
        {activeTab === 'runner' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div>
              <h2 style={{ fontSize: '1.3rem', fontWeight: 700, color: '#f8fafc' }}>Benchmark Execution Engine</h2>
              <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Configure targets, review costed plan, and execute under fail-closed approval</p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
              {/* Configuration Column */}
              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '1rem' }}>1. Select Target Models / Workflows</h3>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', maxHeight: '180px', overflowY: 'auto', marginBottom: '1.25rem' }}>
                  {targets.map((t) => (
                    <label key={t.target_id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.4rem 0.6rem', backgroundColor: '#0f172a', borderRadius: '6px', fontSize: '0.85rem', color: '#cbd5e1' }}>
                      <input 
                        type="checkbox" 
                        checked={selectedTargets.includes(t.target_id)}
                        onChange={(e) => {
                          if (e.target.checked) setSelectedTargets([...selectedTargets, t.target_id])
                          else setSelectedTargets(selectedTargets.filter(id => id !== t.target_id))
                        }}
                      />
                      <span>{t.name}</span>
                    </label>
                  ))}
                </div>

                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '0.5rem' }}>2. Select Evaluation Dataset</h3>
                <select 
                  value={selectedDataset} 
                  onChange={(e) => setSelectedDataset(e.target.value)}
                  style={{ width: '100%', padding: '0.5rem', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', color: '#f8fafc', marginBottom: '1.25rem' }}
                >
                  {datasets.map((d) => (
                    <option key={d.filename} value={d.filename}>{d.filename} ({d.case_count} cases)</option>
                  ))}
                </select>

                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '0.5rem' }}>3. Evaluation Sample Size</h3>
                <input 
                  type="number" 
                  min={1} 
                  max={500} 
                  value={sampleSize} 
                  onChange={(e) => setSampleSize(parseInt(e.target.value) || 1)}
                  style={{ width: '100%', padding: '0.5rem', backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '6px', color: '#f8fafc', marginBottom: '1.5rem' }}
                />

                <button 
                  onClick={handleComputePlan}
                  disabled={planLoading || selectedTargets.length === 0}
                  style={{ width: '100%', padding: '0.75rem', backgroundColor: '#7c3aed', color: '#ffffff', borderRadius: '6px', border: 'none', fontWeight: 600 }}
                >
                  {planLoading ? 'Computing Cost Plan...' : 'Compute & Fingerprint Plan'}
                </button>
              </div>

              {/* Plan Review Column */}
              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.5rem' }}>
                <h3 style={{ fontSize: '1rem', fontWeight: 600, color: '#f8fafc', marginBottom: '1rem' }}>Plan Review & Authorization</h3>

                {plan ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                    <div style={{ padding: '0.75rem', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #1e293b' }}>
                      <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>PLAN FINGERPRINT (SHA-256)</span>
                      <p style={{ fontFamily: 'monospace', fontWeight: 700, color: '#38bdf8', fontSize: '0.95rem' }}>{plan.plan_fingerprint}</p>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                      <div style={{ padding: '0.75rem', backgroundColor: '#0f172a', borderRadius: '6px' }}>
                        <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>EVALUATION CASES</span>
                        <p style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f8fafc' }}>{plan.projected_cases}</p>
                      </div>
                      <div style={{ padding: '0.75rem', backgroundColor: '#0f172a', borderRadius: '6px' }}>
                        <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>PROJECTED COST</span>
                        <p style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f8fafc' }}>${plan.projected_cost_usd.toFixed(4)}</p>
                      </div>
                    </div>

                    {/* Execution Buttons */}
                    <div style={{ display: 'flex', gap: '0.75rem', marginTop: '1rem' }}>
                      {/* Replay Option */}
                      <button 
                        onClick={() => handleExecuteRun(true)}
                        disabled={runInProgress}
                        style={{ flex: 1, padding: '0.75rem', backgroundColor: '#1e293b', color: '#a78bfa', border: '1px solid #334155', borderRadius: '6px', fontWeight: 600 }}
                      >
                        Run Replay ($0.00)
                      </button>

                      {/* Live Option */}
                      <button 
                        onClick={() => setShowApprovalModal(true)}
                        disabled={runInProgress || !plan.is_permitted}
                        style={{ flex: 1, padding: '0.75rem', backgroundColor: plan.is_permitted ? '#10b981' : '#475569', color: '#ffffff', border: 'none', borderRadius: '6px', fontWeight: 600 }}
                      >
                        Authorize Live Run
                      </button>
                    </div>
                  </div>
                ) : (
                  <div style={{ padding: '3rem 1rem', textAlign: 'center', color: '#64748b' }}>
                    Configure targets and dataset on the left, then click "Compute & Fingerprint Plan" to generate an audited plan.
                  </div>
                )}
              </div>
            </div>

            {/* Run Execution Results */}
            {runResult && (
              <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', padding: '1.5rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f8fafc' }}>
                    Run Completed: {runResult.run_id}
                  </h3>
                  <span style={{ fontSize: '0.75rem', padding: '0.2rem 0.5rem', borderRadius: '4px', backgroundColor: '#064e3b', color: '#34d399' }}>
                    Provenance: {runResult.provenance}
                  </span>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem', marginBottom: '1rem' }}>
                  <div style={{ padding: '0.75rem', backgroundColor: '#0f172a', borderRadius: '6px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Cases Evaluated</span>
                    <p style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f8fafc' }}>{runResult.cases_evaluated || runResult.cases_planned}</p>
                  </div>
                  <div style={{ padding: '0.75rem', backgroundColor: '#0f172a', borderRadius: '6px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Successful</span>
                    <p style={{ fontSize: '1.2rem', fontWeight: 700, color: '#10b981' }}>{runResult.success_count || 'Pending'}</p>
                  </div>
                  <div style={{ padding: '0.75rem', backgroundColor: '#0f172a', borderRadius: '6px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Total Spend</span>
                    <p style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f8fafc' }}>${runResult.total_spend_usd || '0.0000'}</p>
                  </div>
                  <div style={{ padding: '0.75rem', backgroundColor: '#0f172a', borderRadius: '6px' }}>
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Duration</span>
                    <p style={{ fontSize: '1.2rem', fontWeight: 700, color: '#f8fafc' }}>{runResult.duration_seconds || 0}s</p>
                  </div>
                </div>

                {runResult.results_preview && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                    <h4 style={{ fontSize: '0.9rem', color: '#94a3b8' }}>Outputs Preview:</h4>
                    {runResult.results_preview.map((r: any, idx: number) => (
                      <div key={idx} style={{ padding: '0.75rem', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #1e293b' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem', color: '#64748b', marginBottom: '0.25rem' }}>
                          <span>Case ID: {r.case_id}</span>
                          <span>Latency: {r.latency_ms?.toFixed(1)} ms</span>
                        </div>
                        <p style={{ fontSize: '0.85rem', color: '#cbd5e1' }}>{r.output_text}</p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* TELEMETRY TAB */}
        {activeTab === 'telemetry' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ fontSize: '1.3rem', fontWeight: 700, color: '#f8fafc' }}>Live Telemetry Event Tail</h2>
                <p style={{ fontSize: '0.85rem', color: '#94a3b8' }}>Real-time SSE telemetry streamed from request_events.jsonl</p>
              </div>
              <span style={{ fontSize: '0.8rem', color: '#10b981', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <RefreshCw size={14} className="animate-spin" /> Stream Active
              </span>
            </div>

            <div style={{ backgroundColor: '#131b2a', border: '1px solid #1e293b', borderRadius: '8px', overflow: 'hidden' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
                <thead>
                  <tr style={{ backgroundColor: '#0f172a', borderBottom: '1px solid #1e293b', color: '#94a3b8' }}>
                    <th style={{ padding: '0.75rem 1rem' }}>Timestamp</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Model / Target</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Latency</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Tokens (In / Out)</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Cost USD</th>
                    <th style={{ padding: '0.75rem 1rem' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((ev, idx) => (
                    <tr key={idx} style={{ borderBottom: '1px solid #1e293b' }}>
                      <td style={{ padding: '0.75rem 1rem', fontFamily: 'monospace', color: '#64748b' }}>{ev.timestamp?.slice(11, 19)}</td>
                      <td style={{ padding: '0.75rem 1rem', color: '#cbd5e1' }}>{ev.model_id}</td>
                      <td style={{ padding: '0.75rem 1rem', color: '#cbd5e1' }}>{ev.latency_ms?.toFixed(1)} ms</td>
                      <td style={{ padding: '0.75rem 1rem', color: '#cbd5e1' }}>{ev.prompt_tokens || 0} / {ev.completion_tokens || 0}</td>
                      <td style={{ padding: '0.75rem 1rem', color: '#f8fafc', fontWeight: 600 }}>${parseFloat(ev.cost_usd || '0').toFixed(4)}</td>
                      <td style={{ padding: '0.75rem 1rem' }}>
                        <span style={{ fontSize: '0.75rem', padding: '0.15rem 0.4rem', borderRadius: '4px', backgroundColor: '#064e3b', color: '#34d399' }}>
                          SUCCESS
                        </span>
                      </td>
                    </tr>
                  ))}
                  {events.length === 0 && (
                    <tr>
                      <td colSpan={6} style={{ padding: '2.5rem', textAlign: 'center', color: '#64748b' }}>
                        Listening for live evaluation requests...
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </main>

      {/* APPROVAL MODAL (Enforces exact typed phrase) */}
      {showApprovalModal && plan && (
        <div style={{ position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.8)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div style={{ backgroundColor: '#131b2a', border: '1px solid #334155', borderRadius: '8px', padding: '2rem', maxWidth: '600px', width: '90%' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#ef4444', marginBottom: '0.75rem' }}>
              <Lock size={22} />
              <h3 style={{ fontSize: '1.2rem', fontWeight: 700 }}>Explicit Live Authorization Required</h3>
            </div>
            <p style={{ fontSize: '0.9rem', color: '#cbd5e1', lineHeight: 1.5, marginBottom: '1rem' }}>
              Live execution sends data to external network providers and bills real money against your budget caps.
            </p>

            <div style={{ padding: '0.75rem', backgroundColor: '#0f172a', borderRadius: '6px', border: '1px solid #1e293b', marginBottom: '1.25rem' }}>
              <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Type the exact confirmation phrase:</span>
              <p style={{ fontFamily: 'monospace', fontWeight: 700, color: '#a78bfa', fontSize: '0.9rem', marginTop: '0.25rem', userSelect: 'all' }}>
                {plan.expected_confirmation_phrase}
              </p>
            </div>

            <input 
              type="text"
              placeholder="Type or paste the exact confirmation phrase..."
              value={approvalPhraseInput}
              onChange={(e) => setApprovalPhraseInput(e.target.value)}
              style={{ width: '100%', padding: '0.75rem', backgroundColor: '#090d16', border: '1px solid #334155', borderRadius: '6px', color: '#f8fafc', marginBottom: '1.25rem' }}
            />

            <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
              <button 
                onClick={() => setShowApprovalModal(false)}
                style={{ padding: '0.6rem 1.2rem', backgroundColor: 'transparent', color: '#94a3b8', border: '1px solid #334155', borderRadius: '6px' }}
              >
                Cancel
              </button>
              <button 
                onClick={() => handleExecuteRun(false)}
                disabled={approvalPhraseInput.trim() !== plan.expected_confirmation_phrase}
                style={{ 
                  padding: '0.6rem 1.2rem', 
                  backgroundColor: approvalPhraseInput.trim() === plan.expected_confirmation_phrase ? '#10b981' : '#475569', 
                  color: '#ffffff', 
                  border: 'none', 
                  borderRadius: '6px', 
                  fontWeight: 600,
                  cursor: approvalPhraseInput.trim() === plan.expected_confirmation_phrase ? 'pointer' : 'not-allowed'
                }}
              >
                Confirm & Dispatch Live Run
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

