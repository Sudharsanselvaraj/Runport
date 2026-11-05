import React, { useState, useEffect } from 'react'
import {
  Sliders,
  Cpu,
  Layers,
  Database,
  FileText,
  Play,
  CheckCircle2,
  GitCompare,
  BarChart2,
  Wallet,
  AlertTriangle,
  ShieldCheck,
  RefreshCw,
  Sun,
  Moon,
  Upload,
  Download,
  Clock,
  Terminal,
  Activity,
  XCircle,
  HelpCircle,
  ChevronRight,
  ExternalLink,
} from 'lucide-react'

// --- Types ---
interface SetupData {
  app_name: string
  version: string
  mode: string
  workspace_root: string
  db_path: string
  db_wal_mode: boolean
  budget_policy: {
    total_budget_usd: number
    pilot_budget_usd: number
    per_run_ceiling_usd: number
    per_case_ceiling_usd: number
    require_priced: boolean
  }
  forbidden_fields: string[]
  dataset_schema: {
    required_fields: Array<{ name: string; type: string; description: string }>
    optional_fields: Array<{ name: string; type: string; description: string }>
    invariants: string[]
  }
}

interface ModelItem {
  model_id: string
  display_name: string
  provider: string
  deployment_mode: string
  license: string
  context_length?: number
  input_price_per_1m_usd: number
  output_price_per_1m_usd: number
  verification_status: string
  experimental_purpose?: string
}

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

interface DatasetSummary {
  filename: string
  path: string
  size_bytes: number
  case_count: number
}

interface DatasetDetail {
  filename: string
  total_cases: number
  cases_preview: any[]
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

interface RunSummary {
  run_id: string
  timestamp: string
  model_id: string
  dataset_path: string
  total_cases: number
  completed_cases: number
  failed_cases: number
  total_cost_usd: string
  mean_latency_ms: number | null
  mean_accuracy?: number | null
  is_dry_run: number
  notes?: string
}

interface ReportData {
  run_id: string
  model_id: string
  dataset_path: string
  timestamp: string
  total_cases: number
  completed_cases: number
  accuracy?: number
  wilson_ci?: [number, number]
  mean_latency_ms?: number
  latency_p50_ms?: number
  latency_p90_ms?: number
  latency_p95_ms?: number
  latency_p99_ms?: number
  mean_prompt_tokens?: number
  mean_completion_tokens?: number
  total_cost_usd: number
  cost_per_1k_cases_usd: number
  cohen_kappa?: number
  confusion_matrix?: {
    labels: string[]
    matrix: number[][]
  }
  classification_report?: Record<string, { precision: number; recall: number; f1: number; support: number }>
}

export default function App() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => {
    return (localStorage.getItem('runport_theme') as 'dark' | 'light') || 'dark'
  })

  const [activeTab, setActiveTab] = useState<
    'setup' | 'models' | 'targets' | 'datasets' | 'plan' | 'liverun' | 'results' | 'compare' | 'reports' | 'budget'
  >(() => {
    const h = window.location.hash.replace('#', '')
    if (['setup', 'models', 'targets', 'datasets', 'plan', 'liverun', 'results', 'compare', 'reports', 'budget'].includes(h)) {
      return h as any
    }
    return 'setup'
  })

  useEffect(() => {
    const onHashChange = () => {
      const h = window.location.hash.replace('#', '')
      if (['setup', 'models', 'targets', 'datasets', 'plan', 'liverun', 'results', 'compare', 'reports', 'budget'].includes(h)) {
        setActiveTab(h as any)
      }
    }
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
  }, [])

  const handleSelectTab = (tab: 'setup' | 'models' | 'targets' | 'datasets' | 'plan' | 'liverun' | 'results' | 'compare' | 'reports' | 'budget') => {
    setActiveTab(tab)
    window.location.hash = tab
  }

  // Global states
  const [loading, setLoading] = useState<boolean>(true)
  const [apiError, setApiError] = useState<string | null>(null)
  const [setup, setSetup] = useState<SetupData | null>(null)
  const [models, setModels] = useState<ModelItem[]>([])
  const [targets, setTargets] = useState<TargetItem[]>([])
  const [datasets, setDatasets] = useState<DatasetSummary[]>([])
  const [budget, setBudget] = useState<BudgetData | null>(null)
  const [runsList, setRunsList] = useState<RunSummary[]>([])
  const [events, setEvents] = useState<any[]>([])

  // Screen 2: Models filter
  const [modelSearch, setModelSearch] = useState<string>('')
  const [verifiedOnly, setVerifiedOnly] = useState<boolean>(false)

  // Screen 3: Target tester
  const [testTargetId, setTestTargetId] = useState<string>('gpt-4o-mini')
  const [testType, setTestType] = useState<string>('raw_model')
  const [testUrl, setTestUrl] = useState<string>('')
  const [testApiKey, setTestApiKey] = useState<string>('')
  const [testPrompt, setTestPrompt] = useState<string>('Explain strict ground truth validation in two concise sentences.')
  const [testingRunning, setTestingRunning] = useState<boolean>(false)
  const [testResult, setTestResult] = useState<any | null>(null)
  // A target probe sends a real, possibly billed request, so the API asks for approval of an exact plan first.
  const [testApproval, setTestApproval] = useState<{
    plan_fingerprint: string
    plan_nonce: string
    expected_confirmation_phrase: string
    message: string
    per_case_cap_usd: string
  } | null>(null)

  // Screen 4: Dataset preview & upload
  const [selectedDatasetDetail, setSelectedDatasetDetail] = useState<DatasetDetail | null>(null)
  const [uploadStatus, setUploadStatus] = useState<string | null>(null)

  // Screen 5: Plan
  const [planSelectedTargets, setPlanSelectedTargets] = useState<string[]>([])
  const [planSelectedDataset, setPlanSelectedDataset] = useState<string>('')
  const [planSampleSize, setPlanSampleSize] = useState<number>(10)
  const [planLoading, setPlanLoading] = useState<boolean>(false)
  const [planData, setPlanData] = useState<PlanData | null>(null)

  // Screen 6: Live run & Replay
  const [runInProgress, setRunInProgress] = useState<boolean>(false)
  const [runResult, setRunResult] = useState<any | null>(null)
  const [showApprovalModal, setShowApprovalModal] = useState<boolean>(false)
  const [approvalUser, setApprovalUser] = useState<string>('Analyst-1')
  const [typedConfirmation, setTypedConfirmation] = useState<string>('')

  // Screen 7: Results
  const [selectedRunId, setSelectedRunId] = useState<string>('')
  const [runDetail, setRunDetail] = useState<any | null>(null)

  // Screen 8: Compare runs
  const [compareRunIdA, setCompareRunIdA] = useState<string>('')
  const [compareRunIdB, setCompareRunIdB] = useState<string>('')
  const [compareReportA, setCompareReportA] = useState<ReportData | null>(null)
  const [compareReportB, setCompareReportB] = useState<ReportData | null>(null)

  // Screen 9: Reports
  const [reportRunId, setReportRunId] = useState<string>('')
  const [reportData, setReportData] = useState<ReportData | null>(null)

  // Screen 10: Budget Reconcile Modal
  const [showReconcileModal, setShowReconcileModal] = useState<boolean>(false)
  const [reconcileTxId, setReconcileTxId] = useState<string>('')
  const [reconcileAmount, setReconcileAmount] = useState<string>('0.0000')
  const [reconcileNotes, setReconcileNotes] = useState<string>('Manual reconciliation approved by operator')

  // Theme effect
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('runport_theme', theme)
  }, [theme])

  const toggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  // Load core data
  const loadInitialData = async () => {
    try {
      setLoading(true)
      const [setupRes, modelsRes, targetsRes, datasetsRes, budgetRes, runsRes] = await Promise.all([
        fetch('/api/setup'),
        fetch('/api/models'),
        fetch('/api/targets'),
        fetch('/api/datasets'),
        fetch('/api/budget'),
        fetch('/api/runs'),
      ])

      if (setupRes.ok) setSetup(await setupRes.json())
      if (modelsRes.ok) setModels(await modelsRes.json())
      if (targetsRes.ok) {
        const tData = await targetsRes.json()
        setTargets(tData)
        if (tData.length > 0 && planSelectedTargets.length === 0) {
          setPlanSelectedTargets([tData[0].target_id])
          setTestTargetId(tData[0].target_id)
        }
      }
      if (datasetsRes.ok) {
        const dData = await datasetsRes.json()
        setDatasets(dData)
        if (dData.length > 0 && !planSelectedDataset) {
          setPlanSelectedDataset(dData[0].filename)
          loadDatasetPreview(dData[0].filename)
        }
      }
      if (budgetRes.ok) setBudget(await budgetRes.json())
      if (runsRes.ok) {
        const rData = await runsRes.json()
        setRunsList(rData)
        if (rData.length > 0) {
          setSelectedRunId(rData[0].run_id)
          loadRunDetail(rData[0].run_id)
          setReportRunId(rData[0].run_id)
          loadReport(rData[0].run_id)
          if (rData.length >= 2) {
            setCompareRunIdA(rData[0].run_id)
            setCompareRunIdB(rData[1].run_id)
            loadCompareReports(rData[0].run_id, rData[1].run_id)
          }
        }
      }
      setApiError(null)
    } catch (err: any) {
      setApiError('Unable to connect to Runport local backend. Ensure `runport web` is active on http://127.0.0.1:8000.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadInitialData()
  }, [])

  // Telemetry SSE stream
  useEffect(() => {
    const es = new EventSource('/api/events')
    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        if (data.type !== 'connected') {
          setEvents((prev) => [data, ...prev].slice(0, 60))
        }
      } catch {}
    }
    return () => es.close()
  }, [])

  // Load dataset preview
  const loadDatasetPreview = async (filename: string) => {
    try {
      const res = await fetch(`/api/datasets/${encodeURIComponent(filename)}`)
      if (res.ok) {
        setSelectedDatasetDetail(await res.json())
      }
    } catch {}
  }

  // Load run detail
  const loadRunDetail = async (runId: string) => {
    if (!runId) return
    try {
      const res = await fetch(`/api/runs/${encodeURIComponent(runId)}`)
      if (res.ok) {
        setRunDetail(await res.json())
      }
    } catch {}
  }

  // Load report data
  const loadReport = async (runId: string) => {
    if (!runId) return
    try {
      const res = await fetch(`/api/reports/${encodeURIComponent(runId)}`)
      if (res.ok) {
        setReportData(await res.json())
      }
    } catch {}
  }

  // Load compare reports
  const loadCompareReports = async (idA: string, idB: string) => {
    if (!idA || !idB) return
    try {
      const [resA, resB] = await Promise.all([
        fetch(`/api/reports/${encodeURIComponent(idA)}`),
        fetch(`/api/reports/${encodeURIComponent(idB)}`),
      ])
      if (resA.ok) setCompareReportA(await resA.json())
      if (resB.ok) setCompareReportB(await resB.json())
    } catch {}
  }

  // Target Tester
  const handleTestTarget = async (approval?: { plan_fingerprint: string; plan_nonce: string }) => {
    setTestingRunning(true)
    setTestResult(null)
    try {
      const res = await fetch('/api/targets/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target: {
            target_id: testTargetId,
            name: testTargetId,
            target_type: testType,
            url: testUrl || undefined,
            api_key: testApiKey || undefined,
          },
          input_payload: { query: testPrompt },
          approve_token: approval?.plan_fingerprint,
          plan_nonce: approval?.plan_nonce,
        }),
      })
      const body = await res.json()
      if (res.status === 428) {
        setTestApproval(body.detail)
        return
      }
      setTestApproval(null)
      if (!res.ok) {
        const detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
        setTestResult({ status: 'failed', error_message: detail })
        return
      }
      setTestResult(body)
    } catch (e: any) {
      setTestResult({ status: 'failed', error_message: e.message })
    } finally {
      setTestingRunning(false)
    }
  }

  // Upload dataset
  const handleDatasetUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    setUploadStatus('Uploading...')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const res = await fetch('/api/datasets/upload', {
        method: 'POST',
        body: fd,
      })
      if (res.ok) {
        setUploadStatus('Dataset uploaded successfully!')
        const updated = await fetch('/api/datasets').then((r) => r.json())
        setDatasets(updated)
      } else {
        const err = await res.json()
        setUploadStatus(`Upload blocked: ${err.detail || 'Path traversal or invalid format'}`)
      }
    } catch (err: any) {
      setUploadStatus(`Error: ${err.message}`)
    }
  }

  // Plan generation
  const handleComputePlan = async () => {
    if (planSelectedTargets.length === 0 || !planSelectedDataset) return
    setPlanLoading(true)
    setPlanData(null)
    try {
      const res = await fetch('/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_ids: planSelectedTargets,
          dataset_name: planSelectedDataset,
          sample_size: planSampleSize > 0 ? planSampleSize : undefined,
          is_pilot: true,
        }),
      })
      const d = await res.json()
      setPlanData(d)
    } catch (e: any) {
      alert(`Failed to compute plan: ${e.message}`)
    } finally {
      setPlanLoading(false)
    }
  }

  // Execute Replay
  const handleExecuteReplay = async () => {
    if (!planData) return
    setRunInProgress(true)
    setRunResult(null)
    try {
      const res = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_ids: planSelectedTargets,
          dataset_name: planSelectedDataset,
          sample_size: planSampleSize,
          plan_fingerprint: planData.plan_fingerprint,
          is_replay: true,
        }),
      })
      const data = await res.json()
      setRunResult(data)
      loadInitialData()
    } catch (e: any) {
      alert(`Replay execution failed: ${e.message}`)
    } finally {
      setRunInProgress(false)
    }
  }

  // Execute Live with single-use approval
  const handleExecuteLive = async () => {
    if (!planData) return
    setRunInProgress(true)
    setRunResult(null)
    setShowApprovalModal(false)

    try {
      // 1. Issue single-use approval token bound to fingerprint
      const approveRes = await fetch('/api/runs/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          plan_fingerprint: planData.plan_fingerprint,
          user: approvalUser,
          timestamp: new Date().toISOString(),
        }),
      })
      if (!approveRes.ok) {
        const err = await approveRes.json()
        throw new Error(err.detail || 'Approval token rejected.')
      }
      const approveData = await approveRes.json()

      // 2. Execute run under spend caps with single-use approval token
      const res = await fetch('/api/runs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_ids: planSelectedTargets,
          dataset_name: planSelectedDataset,
          sample_size: planSampleSize,
          plan_fingerprint: planData.plan_fingerprint,
          is_replay: false,
          approve_token: approveData.approval_token,
        }),
      })
      const data = await res.json()
      setRunResult(data)
      loadInitialData()
    } catch (e: any) {
      alert(`Live run authorization error: ${e.message}`)
    } finally {
      setRunInProgress(false)
    }
  }

  // Budget reconcile
  const handleReconcileSubmit = async () => {
    if (!reconcileTxId) return
    try {
      const res = await fetch('/api/budget/reconcile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          transaction_id: reconcileTxId,
          reconciled_usd: parseFloat(reconcileAmount),
          notes: reconcileNotes,
        }),
      })
      if (res.ok) {
        setShowReconcileModal(false)
        loadInitialData()
      } else {
        const err = await res.json()
        alert(`Reconciliation error: ${err.detail}`)
      }
    } catch (e: any) {
      alert(`Reconciliation error: ${e.message}`)
    }
  }

  return (
    <div>
      {/* Top Header Bar */}
      <header className="header-bar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
          <div
            style={{
              width: 34,
              height: 34,
              borderRadius: 8,
              background: 'linear-gradient(135deg, #38bdf8 0%, #0284c7 100%)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontWeight: 800,
              color: '#0b0f17',
              fontSize: '1.15rem',
            }}
          >
            R
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: '1.05rem', letterSpacing: '-0.02em', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              Runport
              <span className="badge badge-info" style={{ fontSize: '0.65rem' }}>v0.1.0</span>
            </div>
            <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
              Universal Local-First Benchmarking Platform
            </div>
          </div>
        </div>

        {/* Global Status Badges */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
          <div className="badge badge-success" style={{ gap: '0.35rem' }}>
            <ShieldCheck size={13} />
            Local WAL Active
          </div>

          {budget && (
            <div
              className={`badge ${budget.unresolved_count > 0 ? 'badge-danger' : 'badge-info'}`}
              style={{ gap: '0.35rem' }}
            >
              <Wallet size={13} />
              Remaining: ${budget.spend.remaining_total_usd.toFixed(2)}
            </div>
          )}

          <button
            onClick={toggleTheme}
            className="btn btn-secondary"
            style={{ padding: '0.35rem 0.65rem' }}
            title="Toggle theme"
          >
            {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
          </button>

          <button
            onClick={loadInitialData}
            className="btn btn-secondary"
            style={{ padding: '0.35rem 0.65rem' }}
            title="Refresh state"
          >
            <RefreshCw size={15} />
          </button>
        </div>
      </header>

      {/* Main Container */}
      <div className="container">
        {apiError && (
          <div
            className="card"
            style={{
              background: 'rgba(248, 113, 113, 0.1)',
              borderColor: 'var(--accent-red)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
            }}
          >
            <AlertTriangle size={20} color="var(--accent-red)" />
            <div style={{ color: 'var(--accent-red)', fontSize: '0.875rem' }}>{apiError}</div>
          </div>
        )}

        {/* 10 Navigation Tabs */}
        <nav className="nav-tabs">
          <button
            className={`nav-tab ${activeTab === 'setup' ? 'active' : ''}`}
            onClick={() => handleSelectTab('setup')}
          >
            <Sliders size={16} />
            Setup
          </button>
          <button
            className={`nav-tab ${activeTab === 'models' ? 'active' : ''}`}
            onClick={() => handleSelectTab('models')}
          >
            <Cpu size={16} />
            Models
          </button>
          <button
            className={`nav-tab ${activeTab === 'targets' ? 'active' : ''}`}
            onClick={() => handleSelectTab('targets')}
          >
            <Layers size={16} />
            Targets
          </button>
          <button
            className={`nav-tab ${activeTab === 'datasets' ? 'active' : ''}`}
            onClick={() => handleSelectTab('datasets')}
          >
            <Database size={16} />
            Datasets
          </button>
          <button
            className={`nav-tab ${activeTab === 'plan' ? 'active' : ''}`}
            onClick={() => handleSelectTab('plan')}
          >
            <FileText size={16} />
            Plan
          </button>
          <button
            className={`nav-tab ${activeTab === 'liverun' ? 'active' : ''}`}
            onClick={() => handleSelectTab('liverun')}
          >
            <Play size={16} />
            Live Run
          </button>
          <button
            className={`nav-tab ${activeTab === 'results' ? 'active' : ''}`}
            onClick={() => handleSelectTab('results')}
          >
            <CheckCircle2 size={16} />
            Results
          </button>
          <button
            className={`nav-tab ${activeTab === 'compare' ? 'active' : ''}`}
            onClick={() => handleSelectTab('compare')}
          >
            <GitCompare size={16} />
            Compare
          </button>
          <button
            className={`nav-tab ${activeTab === 'reports' ? 'active' : ''}`}
            onClick={() => handleSelectTab('reports')}
          >
            <BarChart2 size={16} />
            Reports
          </button>
          <button
            className={`nav-tab ${activeTab === 'budget' ? 'active' : ''}`}
            onClick={() => handleSelectTab('budget')}
          >
            <Wallet size={16} />
            Budget
          </button>
        </nav>

        {/* ----------------- SCREEN 1: SETUP ----------------- */}
        {activeTab === 'setup' && setup && (
          <div>
            <div className="card">
              <div className="card-title">
                <Sliders size={18} color="var(--accent-blue)" />
                Workspace Environment & Storage Architecture
              </div>
              <div className="card-subtitle">
                Inspect local paths, SQLite append-only WAL mode, and runtime parameters.
              </div>
              <div className="grid-3">
                <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Workspace Root</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '0.775rem', wordBreak: 'break-all' }}>{setup.workspace_root}</div>
                </div>
                <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Database Path (WAL)</div>
                  <div style={{ fontFamily: 'monospace', fontSize: '0.775rem', wordBreak: 'break-all' }}>{setup.db_path}</div>
                </div>
                <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Execution Mode</div>
                  <div style={{ fontWeight: 600, color: 'var(--accent-green)' }}>
                    Local-First Offline / Sockets Controlled
                  </div>
                </div>
              </div>
            </div>

            <div className="card">
              <div className="card-title">
                <ShieldCheck size={18} color="var(--accent-green)" />
                Active Spend Caps & Fail-Closed Guardrails
              </div>
              <div className="grid-4" style={{ marginBottom: '1.25rem' }}>
                <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Total Spend Cap</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>${setup.budget_policy.total_budget_usd.toFixed(2)}</div>
                </div>
                <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Pilot Spend Cap</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>${setup.budget_policy.pilot_budget_usd.toFixed(2)}</div>
                </div>
                <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Per-Run Ceiling</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>${setup.budget_policy.per_run_ceiling_usd.toFixed(2)}</div>
                </div>
                <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Per-Case Ceiling</div>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>${setup.budget_policy.per_case_ceiling_usd.toFixed(2)}</div>
                </div>
              </div>
            </div>

            <div className="grid-2">
              <div className="card">
                <div className="card-title">Forbidden PII Fields</div>
                <div className="card-subtitle">
                  Fields automatically blocked and redacted prior to execution or export.
                </div>
                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                  {setup.forbidden_fields.map((f) => (
                    <span key={f} className="badge badge-warning">
                      {f}
                    </span>
                  ))}
                </div>
              </div>

              <div className="card">
                <div className="card-title">Dataset Specification Schema</div>
                <div className="card-subtitle">
                  Schema required for zero-leakage, reproducible benchmarks.
                </div>
                <ul style={{ fontSize: '0.825rem', paddingLeft: '1.25rem', color: 'var(--text-secondary)' }}>
                  {setup.dataset_schema.required_fields.map((req) => (
                    <li key={req.name} style={{ marginBottom: '0.25rem' }}>
                      <code style={{ color: 'var(--accent-blue)' }}>{req.name}</code> ({req.type}): {req.description}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        )}

        {/* ----------------- SCREEN 2: MODELS ----------------- */}
        {activeTab === 'models' && (
          <div className="card">
            <div className="card-title">
              <Cpu size={18} color="var(--accent-blue)" />
              Model Portfolio Registry & Fact Verification
            </div>
            <div className="card-subtitle">
              Sourced catalog rates with explicit verification status. Unverified or missing rates are never defaulted to zero.
            </div>

            <div style={{ display: 'flex', gap: '0.85rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
              <input
                type="text"
                className="input"
                style={{ maxWidth: 300 }}
                placeholder="Search models, providers, licenses..."
                value={modelSearch}
                onChange={(e) => setModelSearch(e.target.value)}
              />
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={verifiedOnly}
                  onChange={(e) => setVerifiedOnly(e.target.checked)}
                />
                Primary Verified Facts Only
              </label>
            </div>

            <div className="table-wrapper">
              <table className="table">
                <thead>
                  <tr>
                    <th>Model Identifier</th>
                    <th>Vendor / Provider</th>
                    <th>Context Limit</th>
                    <th>Input / 1M USD</th>
                    <th>Output / 1M USD</th>
                    <th>Fact Verification Status</th>
                    <th>License</th>
                  </tr>
                </thead>
                <tbody>
                  {models
                    .filter((m) => {
                      const matchesSearch =
                        m.model_id.toLowerCase().includes(modelSearch.toLowerCase()) ||
                        m.display_name.toLowerCase().includes(modelSearch.toLowerCase()) ||
                        m.provider.toLowerCase().includes(modelSearch.toLowerCase())
                      const matchesVerified = !verifiedOnly || m.verification_status.includes('VERIFIED')
                      return matchesSearch && matchesVerified
                    })
                    .map((m) => (
                      <tr key={m.model_id}>
                        <td>
                          <div style={{ fontWeight: 600 }}>{m.display_name}</div>
                          <div style={{ fontSize: '0.725rem', fontFamily: 'monospace', color: 'var(--text-muted)' }}>{m.model_id}</div>
                        </td>
                        <td>{m.provider}</td>
                        <td>{m.context_length ? `${(m.context_length / 1000).toFixed(0)}k tokens` : 'None'}</td>
                        <td style={{ fontFamily: 'monospace' }}>${m.input_price_per_1m_usd.toFixed(4)}</td>
                        <td style={{ fontFamily: 'monospace' }}>${m.output_price_per_1m_usd.toFixed(4)}</td>
                        <td>
                          <span
                            className={`badge ${
                              m.verification_status.includes('PRIMARY')
                                ? 'badge-success'
                                : m.verification_status.includes('USER')
                                ? 'badge-warning'
                                : 'badge-info'
                            }`}
                          >
                            {m.verification_status}
                          </span>
                        </td>
                        <td>{m.license}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* ----------------- SCREEN 3: TARGETS & TESTER ----------------- */}
        {activeTab === 'targets' && (
          <div>
            <div className="card">
              <div className="card-title">
                <Layers size={18} color="var(--accent-blue)" />
                Interactive Target & Connector Tester
              </div>
              <div className="card-subtitle">
                Directly exercise raw LLMs, HTTP endpoints, Dify, Ollama, Flowise, or custom workflows with secret scrubbing.
              </div>

              <div className="grid-2">
                <div>
                  <div className="form-group">
                    <label className="form-label">Target Identifier</label>
                    <input
                      type="text"
                      className="input"
                      value={testTargetId}
                      onChange={(e) => setTestTargetId(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Connector Protocol</label>
                    <select
                      className="select"
                      value={testType}
                      onChange={(e) => setTestType(e.target.value)}
                    >
                      <option value="raw_model">Raw LLM (OpenAI-Compatible / OpenRouter)</option>
                      <option value="http">Generic HTTP Workflow</option>
                      <option value="dify">Dify Chat & Workflow</option>
                      <option value="ollama">Local Ollama</option>
                      <option value="flowise">Flowise Connector</option>
                      <option value="langflow">Langflow Connector</option>
                      <option value="n8n">n8n Webhook</option>
                      <option value="langgraph">LangGraph Server</option>
                    </select>
                  </div>

                  {testType !== 'raw_model' && (
                    <div className="form-group">
                      <label className="form-label">Endpoint URL (SSRF Protected)</label>
                      <input
                        type="text"
                        className="input"
                        placeholder="https://api.example.com/v1/run"
                        value={testUrl}
                        onChange={(e) => setTestUrl(e.target.value)}
                      />
                    </div>
                  )}

                  <div className="form-group">
                    <label className="form-label">API Key / Token (Scrubbed)</label>
                    <input
                      type="password"
                      className="input"
                      placeholder="Optional bearer token"
                      value={testApiKey}
                      onChange={(e) => setTestApiKey(e.target.value)}
                    />
                  </div>

                  <div className="form-group">
                    <label className="form-label">Input Query / Prompt</label>
                    <textarea
                      className="textarea"
                      rows={3}
                      value={testPrompt}
                      onChange={(e) => setTestPrompt(e.target.value)}
                    />
                  </div>

                  <button
                    className="btn btn-primary"
                    onClick={() => handleTestTarget()}
                    disabled={testingRunning}
                  >
                    {testingRunning ? <RefreshCw className="animate-spin" size={15} /> : <Play size={15} />}
                    Execute Probe Test
                  </button>

                  {testApproval && (
                    <div style={{ marginTop: '1rem', padding: '0.75rem', borderRadius: 6, border: '1px solid var(--border-color)', background: 'var(--bg-input)', fontSize: '0.8rem' }}>
                      <div style={{ fontWeight: 600, marginBottom: '0.25rem' }}>Approval required</div>
                      <div style={{ marginBottom: '0.5rem' }}>{testApproval.message}</div>
                      <div style={{ color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                        Spend cap for this request: ${testApproval.per_case_cap_usd}. Plan{' '}
                        <code>{testApproval.plan_fingerprint.slice(0, 16)}</code>
                      </div>
                      <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <button className="btn btn-primary" onClick={() => handleTestTarget(testApproval)} disabled={testingRunning}>
                          Approve and send
                        </button>
                        <button className="btn" onClick={() => setTestApproval(null)} disabled={testingRunning}>
                          Cancel
                        </button>
                      </div>
                    </div>
                  )}
                </div>

                <div>
                  <div className="form-label">Probe Execution Result</div>
                  {testResult ? (
                    <div style={{ background: 'var(--bg-input)', padding: '1rem', borderRadius: 6, border: '1px solid var(--border-color)', minHeight: 280 }}>
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                        <span className={`badge ${testResult.is_success ? 'badge-success' : 'badge-danger'}`}>
                          Status: {testResult.status}
                        </span>
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                          Cost Basis: {testResult.cost_basis || 'UNAVAILABLE'}
                        </span>
                      </div>

                      <div className="grid-3" style={{ marginBottom: '0.75rem', fontSize: '0.8rem' }}>
                        <div>Latency: <strong>{testResult.latency_ms ? `${testResult.latency_ms.toFixed(1)} ms` : 'None'}</strong></div>
                        <div>Tokens In: <strong>{testResult.tokens_in ?? 'None'}</strong></div>
                        <div>Tokens Out: <strong>{testResult.tokens_out ?? 'None'}</strong></div>
                      </div>

                      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '0.25rem' }}>
                        Generated Output:
                      </div>
                      <div
                        style={{
                          background: 'var(--bg-card)',
                          padding: '0.75rem',
                          borderRadius: 4,
                          fontSize: '0.825rem',
                          fontFamily: 'monospace',
                          whiteSpace: 'pre-wrap',
                          maxHeight: 180,
                          overflowY: 'auto',
                        }}
                      >
                        {testResult.output_text || testResult.error_message || 'No response output.'}
                      </div>
                    </div>
                  ) : (
                    <div
                      style={{
                        background: 'var(--bg-input)',
                        padding: '2rem',
                        borderRadius: 6,
                        border: '1px dashed var(--border-color)',
                        textAlign: 'center',
                        color: 'var(--text-muted)',
                        fontSize: '0.85rem',
                      }}
                    >
                      Run a probe test to inspect response latency, tokens, cost basis, and scrubbed payload output.
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ----------------- SCREEN 4: DATASETS ----------------- */}
        {activeTab === 'datasets' && (
          <div className="grid-2">
            <div>
              <div className="card">
                <div className="card-title">
                  <Database size={18} color="var(--accent-blue)" />
                  Evaluation Datasets
                </div>
                <div className="card-subtitle">
                  Datasets stored in data/evaluation/. Source datasets are immutably hashed with SHA-256 before evaluation.
                </div>

                <div className="table-wrapper" style={{ marginBottom: '1.25rem' }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Filename</th>
                        <th>Cases</th>
                        <th>File Size</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {datasets.map((d) => (
                        <tr key={d.filename}>
                          <td>
                            <strong>{d.filename}</strong>
                          </td>
                          <td>{d.case_count}</td>
                          <td>{(d.size_bytes / 1024).toFixed(1)} KB</td>
                          <td>
                            <button
                              className="btn btn-secondary"
                              style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
                              onClick={() => loadDatasetPreview(d.filename)}
                            >
                              Inspect Rows
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div style={{ background: 'var(--bg-input)', padding: '1rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Safe Dataset Upload</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>
                    Files are validated against path traversal (../) and saved strictly inside data/evaluation/.
                  </div>
                  <input
                    type="file"
                    accept=".jsonl,.csv,.json"
                    onChange={handleDatasetUpload}
                    style={{ fontSize: '0.8rem' }}
                  />
                  {uploadStatus && (
                    <div style={{ marginTop: '0.5rem', fontSize: '0.8rem', color: 'var(--accent-blue)' }}>
                      {uploadStatus}
                    </div>
                  )}
                </div>
              </div>
            </div>

            <div>
              <div className="card">
                <div className="card-title">Case Preview</div>
                <div className="card-subtitle">
                  {selectedDatasetDetail
                    ? `Showing sample rows for ${selectedDatasetDetail.filename} (${selectedDatasetDetail.total_cases} total cases)`
                    : 'Select a dataset to preview evaluation cases.'}
                </div>

                {selectedDatasetDetail ? (
                  <div className="table-wrapper" style={{ maxHeight: 480, overflowY: 'auto' }}>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>ID</th>
                          <th>Prompt Query</th>
                          <th>Ground Truth</th>
                        </tr>
                      </thead>
                      <tbody>
                        {selectedDatasetDetail.cases_preview.map((c, i) => (
                          <tr key={i}>
                            <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>
                              {c.case_id || c.id || i + 1}
                            </td>
                            <td style={{ fontSize: '0.8rem' }}>{c.query || c.input || '-'}</td>
                            <td style={{ fontSize: '0.8rem', color: 'var(--accent-green)' }}>
                              {c.ground_truth || c.expected || '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                    No dataset selected.
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ----------------- SCREEN 5: PLAN ----------------- */}
        {activeTab === 'plan' && (
          <div className="card">
            <div className="card-title">
              <FileText size={18} color="var(--accent-blue)" />
              Benchmark Execution Planner & Cryptographic Fingerprint
            </div>
            <div className="card-subtitle">
              Calculates pessimistic upper-bound spend before live execution. Live runs are refused fail-closed if spend exceeds policy caps.
            </div>

            <div className="grid-3" style={{ marginBottom: '1.25rem' }}>
              <div className="form-group">
                <label className="form-label">Candidate Targets</label>
                <div style={{ background: 'var(--bg-input)', padding: '0.5rem', borderRadius: 6, maxHeight: 150, overflowY: 'auto', border: '1px solid var(--border-color)' }}>
                  {targets.map((t) => (
                    <label key={t.target_id} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.8rem', padding: '0.2rem 0', cursor: 'pointer' }}>
                      <input
                        type="checkbox"
                        checked={planSelectedTargets.includes(t.target_id)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setPlanSelectedTargets([...planSelectedTargets, t.target_id])
                          } else {
                            setPlanSelectedTargets(planSelectedTargets.filter((id) => id !== t.target_id))
                          }
                        }}
                      />
                      {t.name}
                    </label>
                  ))}
                </div>
              </div>

              <div className="form-group">
                <label className="form-label">Evaluation Dataset</label>
                <select
                  className="select"
                  value={planSelectedDataset}
                  onChange={(e) => setPlanSelectedDataset(e.target.value)}
                >
                  {datasets.map((d) => (
                    <option key={d.filename} value={d.filename}>
                      {d.filename} ({d.case_count} cases)
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group">
                <label className="form-label">Sample Size Limit</label>
                <input
                  type="number"
                  className="input"
                  min={1}
                  value={planSampleSize}
                  onChange={(e) => setPlanSampleSize(parseInt(e.target.value) || 1)}
                />
              </div>
            </div>

            <button
              className="btn btn-primary"
              onClick={handleComputePlan}
              disabled={planLoading || planSelectedTargets.length === 0}
              style={{ marginBottom: '1.25rem' }}
            >
              {planLoading ? <RefreshCw className="animate-spin" size={15} /> : <FileText size={15} />}
              Compute Cryptographic Plan
            </button>

            {planData && (
              <div style={{ background: 'var(--bg-input)', padding: '1.25rem', borderRadius: 8, border: '1px solid var(--border-color)' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap' }}>
                  <div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>SHA-256 Plan Fingerprint</div>
                    <div style={{ fontFamily: 'monospace', fontSize: '1.1rem', fontWeight: 700, color: 'var(--accent-blue)' }}>
                      {planData.plan_fingerprint}
                    </div>
                  </div>
                  <div>
                    <span className={`badge ${planData.is_permitted ? 'badge-success' : 'badge-danger'}`} style={{ fontSize: '0.85rem' }}>
                      {planData.is_permitted ? 'Preflight Check: PERMITTED' : 'Preflight Check: BLOCKED'}
                    </span>
                  </div>
                </div>

                {!planData.is_permitted && (
                  <div
                    style={{
                      background: 'rgba(248, 113, 113, 0.15)',
                      padding: '0.75rem',
                      borderRadius: 6,
                      border: '1px solid var(--accent-red)',
                      marginBottom: '1rem',
                      color: 'var(--accent-red)',
                      fontSize: '0.85rem',
                    }}
                  >
                    <strong>Budget Exceeded / Preflight Blockers:</strong>
                    <ul style={{ paddingLeft: '1.25rem', marginTop: '0.25rem' }}>
                      {planData.blockers.map((b, i) => (
                        <li key={i}>{b}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="grid-3" style={{ marginBottom: '1rem' }}>
                  <div>Projected Cases: <strong>{planData.projected_cases}</strong></div>
                  <div>Projected Upper Spend: <strong>${planData.projected_cost_usd.toFixed(4)}</strong></div>
                  <div>Dataset: <strong>{planData.dataset_name}</strong></div>
                </div>

                <div className="table-wrapper">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Target Model / Endpoint</th>
                        <th>Input / 1M</th>
                        <th>Output / 1M</th>
                        <th>Projected Upper Spend</th>
                      </tr>
                    </thead>
                    <tbody>
                      {planData.targets.map((t, idx) => (
                        <tr key={idx}>
                          <td><strong>{t.display_name}</strong></td>
                          <td>{t.input_price_per_1m ? `$${t.input_price_per_1m.toFixed(4)}` : 'None'}</td>
                          <td>{t.output_price_per_1m ? `$${t.output_price_per_1m.toFixed(4)}` : 'None'}</td>
                          <td style={{ fontFamily: 'monospace' }}>${t.projected_cost_usd.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ----------------- SCREEN 6: LIVE RUN & REPLAY ----------------- */}
        {activeTab === 'liverun' && (
          <div className="grid-2">
            <div>
              <div className="card">
                <div className="card-title">
                  <Play size={18} color="var(--accent-blue)" />
                  Benchmark Execution Runner
                </div>
                <div className="card-subtitle">
                  Launch runs under fail-closed budget caps, or execute deterministic Replays with zero live spend.
                </div>

                {planData ? (
                  <div style={{ background: 'var(--bg-input)', padding: '1rem', borderRadius: 6, marginBottom: '1.25rem', border: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Active Plan Fingerprint</div>
                    <div style={{ fontFamily: 'monospace', fontWeight: 600, color: 'var(--accent-blue)' }}>
                      {planData.plan_fingerprint}
                    </div>
                    <div style={{ fontSize: '0.8rem', marginTop: '0.4rem' }}>
                      Targets: <strong>{planSelectedTargets.join(', ')}</strong> | Cases: <strong>{planData.projected_cases}</strong>
                    </div>
                  </div>
                ) : (
                  <div style={{ background: 'var(--bg-input)', padding: '1rem', borderRadius: 6, marginBottom: '1.25rem', border: '1px dashed var(--border-color)', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                    No computed plan selected. Navigate to the <strong>Plan</strong> tab to compute a plan fingerprint first.
                  </div>
                )}

                <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
                  <button
                    className="btn btn-secondary"
                    onClick={handleExecuteReplay}
                    disabled={runInProgress || !planData}
                  >
                    <RefreshCw size={15} />
                    Run Isolated Replay ($0.00 Spend)
                  </button>

                  <button
                    className="btn btn-primary"
                    onClick={() => setShowApprovalModal(true)}
                    disabled={runInProgress || !planData || !planData.is_permitted}
                  >
                    <Play size={15} />
                    Authorize & Run Live Benchmark
                  </button>
                </div>

                {runInProgress && (
                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-blue)', fontSize: '0.85rem' }}>
                    <RefreshCw className="animate-spin" size={16} />
                    Benchmark execution active under ledger spend caps...
                  </div>
                )}

                {runResult && (
                  <div style={{ background: 'var(--bg-input)', padding: '1rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                      <strong>Execution Complete</strong>
                      <span className="badge badge-success">Provenance: {runResult.provenance}</span>
                    </div>
                    <div style={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>
                      Run ID: {runResult.run_id} | Total Cases: {runResult.cases_evaluated || runResult.cases_planned} | Spend: ${runResult.total_spend_usd || '0.0000'}
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div>
              <div className="card">
                <div className="card-title">
                  <Activity size={18} color="var(--accent-green)" />
                  Live SSE Telemetry Event Stream
                </div>
                <div className="card-subtitle">
                  Real-time Server-Sent Events tailing local append-only request logs.
                </div>

                <div
                  style={{
                    background: 'var(--bg-input)',
                    padding: '0.75rem',
                    borderRadius: 6,
                    height: 380,
                    overflowY: 'auto',
                    fontFamily: 'monospace',
                    fontSize: '0.75rem',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  {events.length === 0 ? (
                    <div style={{ color: 'var(--text-muted)', textAlign: 'center', paddingTop: '2rem' }}>
                      Awaiting live request telemetry events...
                    </div>
                  ) : (
                    events.map((ev, idx) => (
                      <div
                        key={idx}
                        style={{
                          borderBottom: '1px solid var(--border-color)',
                          padding: '0.4rem 0',
                          display: 'flex',
                          justifyContent: 'space-between',
                          gap: '0.5rem',
                        }}
                      >
                        <div>
                          <span style={{ color: 'var(--accent-blue)' }}>[{ev.model_id || 'system'}]</span>{' '}
                          <span>{ev.status || 'OK'}</span>{' '}
                          {ev.latency_ms && <span style={{ color: 'var(--text-muted)' }}>({ev.latency_ms.toFixed(0)}ms)</span>}
                        </div>
                        <div style={{ color: 'var(--text-muted)' }}>{ev.timestamp ? ev.timestamp.slice(11, 19) : ''}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ----------------- SCREEN 7: RESULTS ----------------- */}
        {activeTab === 'results' && (
          <div>
            <div className="card">
              <div className="card-title">
                <CheckCircle2 size={18} color="var(--accent-green)" />
                Benchmark Results Explorer
              </div>
              <div className="card-subtitle">
                Inspect run headers, case-by-case outputs, latencies, tokens, and cost basis.
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '1.25rem', flexWrap: 'wrap' }}>
                <label className="form-label" style={{ margin: 0 }}>Select Evaluation Run:</label>
                <select
                  className="select"
                  style={{ maxWidth: 360 }}
                  value={selectedRunId}
                  onChange={(e) => {
                    setSelectedRunId(e.target.value)
                    loadRunDetail(e.target.value)
                  }}
                >
                  {runsList.map((r) => (
                    <option key={r.run_id} value={r.run_id}>
                      {r.run_id} ({r.model_id} - {r.total_cases} cases - {r.timestamp.slice(0, 10)})
                    </option>
                  ))}
                </select>
              </div>

              {runDetail && runDetail.run && (
                <div>
                  <div className="grid-4" style={{ marginBottom: '1.25rem' }}>
                    <div style={{ background: 'var(--bg-input)', padding: '0.75rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                      <div className="form-label">Evaluated Model</div>
                      <div style={{ fontWeight: 600 }}>{runDetail.run.model_id}</div>
                    </div>
                    <div style={{ background: 'var(--bg-input)', padding: '0.75rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                      <div className="form-label">Total Cases</div>
                      <div style={{ fontWeight: 600 }}>{runDetail.run.total_cases}</div>
                    </div>
                    <div style={{ background: 'var(--bg-input)', padding: '0.75rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                      <div className="form-label">Mean Latency</div>
                      <div style={{ fontWeight: 600 }}>{runDetail.run.mean_latency_ms != null ? `${runDetail.run.mean_latency_ms.toFixed(1)} ms` : '—'}</div>
                    </div>
                    <div style={{ background: 'var(--bg-input)', padding: '0.75rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                      <div className="form-label">Total Spent</div>
                      <div style={{ fontWeight: 600 }}>${parseFloat(runDetail.run.total_cost_usd).toFixed(4)}</div>
                    </div>
                  </div>

                  <div className="table-wrapper" style={{ maxHeight: 500, overflowY: 'auto' }}>
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Case ID</th>
                          <th>Prompt Preview</th>
                          <th>Generated Output</th>
                          <th>Latency</th>
                          <th>Tokens (In/Out)</th>
                          <th>Cost USD</th>
                          <th>Accuracy</th>
                        </tr>
                      </thead>
                      <tbody>
                        {runDetail.results.map((res: any) => (
                          <tr key={res.result_id}>
                            <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{res.case_id}</td>
                            <td style={{ fontSize: '0.775rem', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {res.prompt}
                            </td>
                            <td style={{ fontSize: '0.775rem', maxWidth: 260, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {res.generated_output}
                            </td>
                            <td>{res.latency_ms ? `${res.latency_ms.toFixed(0)} ms` : 'None'}</td>
                            <td>
                              {res.prompt_tokens ?? 'None'} / {res.completion_tokens ?? 'None'}
                            </td>
                            <td style={{ fontFamily: 'monospace' }}>
                              {res.cost_usd ? `$${parseFloat(res.cost_usd).toFixed(4)}` : 'None'}
                            </td>
                            <td>
                              {res.accuracy !== null && res.accuracy !== undefined ? (
                                <span className={`badge ${res.accuracy >= 1.0 ? 'badge-success' : 'badge-danger'}`}>
                                  {res.accuracy >= 1.0 ? 'MATCH' : 'MISMATCH'}
                                </span>
                              ) : (
                                <span className="badge badge-info">UNSCORED</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ----------------- SCREEN 8: COMPARE RUNS ----------------- */}
        {activeTab === 'compare' && (
          <div className="card">
            <div className="card-title">
              <GitCompare size={18} color="var(--accent-blue)" />
              Head-to-Head Benchmark Run Comparison
            </div>
            <div className="card-subtitle">
              Compare two runs across accuracy, latency distributions, spend deltas, and responsive SVG charts.
            </div>

            <div className="grid-2" style={{ marginBottom: '1.25rem' }}>
              <div>
                <label className="form-label">Baseline Run (A)</label>
                <select
                  className="select"
                  value={compareRunIdA}
                  onChange={(e) => {
                    setCompareRunIdA(e.target.value)
                    loadCompareReports(e.target.value, compareRunIdB)
                  }}
                >
                  {runsList.map((r) => (
                    <option key={r.run_id} value={r.run_id}>
                      {r.run_id} ({r.model_id})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="form-label">Candidate Run (B)</label>
                <select
                  className="select"
                  value={compareRunIdB}
                  onChange={(e) => {
                    setCompareRunIdB(e.target.value)
                    loadCompareReports(compareRunIdA, e.target.value)
                  }}
                >
                  {runsList.map((r) => (
                    <option key={r.run_id} value={r.run_id}>
                      {r.run_id} ({r.model_id})
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {compareReportA && compareReportB && (
              <div>
                <div className="table-wrapper" style={{ marginBottom: '1.5rem' }}>
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Metric Dimension</th>
                        <th>Run A ({compareReportA.model_id})</th>
                        <th>Run B ({compareReportB.model_id})</th>
                        <th>Delta (B - A)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td><strong>Supervised Accuracy</strong></td>
                        <td>{compareReportA.accuracy !== null && compareReportA.accuracy !== undefined ? `${(compareReportA.accuracy * 100).toFixed(1)}%` : 'None'}</td>
                        <td>{compareReportB.accuracy !== null && compareReportB.accuracy !== undefined ? `${(compareReportB.accuracy * 100).toFixed(1)}%` : 'None'}</td>
                        <td style={{ color: (compareReportB.accuracy || 0) >= (compareReportA.accuracy || 0) ? 'var(--accent-green)' : 'var(--accent-red)' }}>
                          {compareReportA.accuracy !== null && compareReportA.accuracy !== undefined && compareReportB.accuracy !== null && compareReportB.accuracy !== undefined
                            ? `${((compareReportB.accuracy - compareReportA.accuracy) * 100).toFixed(1)}%`
                            : '-'}
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Mean Latency</strong></td>
                        <td>{compareReportA.mean_latency_ms ? `${compareReportA.mean_latency_ms.toFixed(1)} ms` : 'None'}</td>
                        <td>{compareReportB.mean_latency_ms ? `${compareReportB.mean_latency_ms.toFixed(1)} ms` : 'None'}</td>
                        <td style={{ color: (compareReportB.mean_latency_ms || 0) <= (compareReportA.mean_latency_ms || 0) ? 'var(--accent-green)' : 'var(--accent-amber)' }}>
                          {compareReportA.mean_latency_ms && compareReportB.mean_latency_ms
                            ? `${(compareReportB.mean_latency_ms - compareReportA.mean_latency_ms).toFixed(1)} ms`
                            : '-'}
                        </td>
                      </tr>
                      <tr>
                        <td><strong>p95 Latency</strong></td>
                        <td>{compareReportA.latency_p95_ms ? `${compareReportA.latency_p95_ms.toFixed(1)} ms` : 'None'}</td>
                        <td>{compareReportB.latency_p95_ms ? `${compareReportB.latency_p95_ms.toFixed(1)} ms` : 'None'}</td>
                        <td>
                          {compareReportA.latency_p95_ms && compareReportB.latency_p95_ms
                            ? `${(compareReportB.latency_p95_ms - compareReportA.latency_p95_ms).toFixed(1)} ms`
                            : '-'}
                        </td>
                      </tr>
                      <tr>
                        <td><strong>Cost per 1k Queries</strong></td>
                        <td style={{ fontFamily: 'monospace' }}>${compareReportA.cost_per_1k_cases_usd.toFixed(4)}</td>
                        <td style={{ fontFamily: 'monospace' }}>${compareReportB.cost_per_1k_cases_usd.toFixed(4)}</td>
                        <td style={{ fontFamily: 'monospace' }}>
                          ${(compareReportB.cost_per_1k_cases_usd - compareReportA.cost_per_1k_cases_usd).toFixed(4)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* SVG Visual Comparison Charts */}
                <div className="grid-2">
                  <div style={{ background: 'var(--bg-input)', padding: '1rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                    <div className="form-label" style={{ marginBottom: '0.75rem' }}>Latency Distribution Comparison (ms)</div>
                    <svg viewBox="0 0 400 160" width="100%" height="160">
                      <rect x="0" y="0" width="400" height="160" fill="transparent" />
                      {/* Bars for Run A */}
                      <rect x="60" y={140 - Math.min(120, (compareReportA.mean_latency_ms || 50) * 0.4)} width="40" height={Math.min(120, (compareReportA.mean_latency_ms || 50) * 0.4)} fill="#38bdf8" rx="4" />
                      <rect x="110" y={140 - Math.min(120, (compareReportA.latency_p95_ms || 90) * 0.4)} width="40" height={Math.min(120, (compareReportA.latency_p95_ms || 90) * 0.4)} fill="#0284c7" rx="4" />

                      {/* Bars for Run B */}
                      <rect x="230" y={140 - Math.min(120, (compareReportB.mean_latency_ms || 50) * 0.4)} width="40" height={Math.min(120, (compareReportB.mean_latency_ms || 50) * 0.4)} fill="#34d399" rx="4" />
                      <rect x="280" y={140 - Math.min(120, (compareReportB.latency_p95_ms || 90) * 0.4)} width="40" height={Math.min(120, (compareReportB.latency_p95_ms || 90) * 0.4)} fill="#059669" rx="4" />

                      <line x1="20" y1="140" x2="380" y2="140" stroke="var(--border-color)" strokeWidth="1" />
                      <text x="85" y="155" fill="var(--text-secondary)" fontSize="10" textAnchor="middle">Run A (Mean / p95)</text>
                      <text x="275" y="155" fill="var(--text-secondary)" fontSize="10" textAnchor="middle">Run B (Mean / p95)</text>
                    </svg>
                  </div>

                  <div style={{ background: 'var(--bg-input)', padding: '1rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                    <div className="form-label" style={{ marginBottom: '0.75rem' }}>Spend per 1k Inferences ($)</div>
                    <svg viewBox="0 0 400 160" width="100%" height="160">
                      <rect x="0" y="0" width="400" height="160" fill="transparent" />
                      <rect x="80" y={140 - Math.min(120, compareReportA.cost_per_1k_cases_usd * 200 + 10)} width="60" height={Math.min(120, compareReportA.cost_per_1k_cases_usd * 200 + 10)} fill="#38bdf8" rx="4" />
                      <rect x="250" y={140 - Math.min(120, compareReportB.cost_per_1k_cases_usd * 200 + 10)} width="60" height={Math.min(120, compareReportB.cost_per_1k_cases_usd * 200 + 10)} fill="#34d399" rx="4" />

                      <line x1="20" y1="140" x2="380" y2="140" stroke="var(--border-color)" strokeWidth="1" />
                      <text x="110" y="155" fill="var(--text-secondary)" fontSize="10" textAnchor="middle">Run A (${compareReportA.cost_per_1k_cases_usd.toFixed(3)})</text>
                      <text x="280" y="155" fill="var(--text-secondary)" fontSize="10" textAnchor="middle">Run B (${compareReportB.cost_per_1k_cases_usd.toFixed(3)})</text>
                    </svg>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ----------------- SCREEN 9: REPORTS ----------------- */}
        {activeTab === 'reports' && (
          <div>
            <div className="card">
              <div className="card-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <BarChart2 size={18} color="var(--accent-blue)" />
                  Statistical Evaluation Report & Sanitized Traces
                </div>
                <a
                  href="/api/reports/export-traces?format=zip"
                  className="btn btn-secondary"
                  style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
                >
                  <Download size={14} />
                  Export Sanitized Traces (.ZIP)
                </a>
              </div>
              <div className="card-subtitle">
                Supervised metrics with Wilson score intervals, Cohen's Kappa, and per-class classification matrices.
              </div>

              <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center', marginBottom: '1.25rem' }}>
                <label className="form-label" style={{ margin: 0 }}>Select Run:</label>
                <select
                  className="select"
                  style={{ maxWidth: 360 }}
                  value={reportRunId}
                  onChange={(e) => {
                    setReportRunId(e.target.value)
                    loadReport(e.target.value)
                  }}
                >
                  {runsList.map((r) => (
                    <option key={r.run_id} value={r.run_id}>
                      {r.run_id} ({r.model_id})
                    </option>
                  ))}
                </select>
              </div>

              {reportData && (
                <div>
                  <div className="grid-4" style={{ marginBottom: '1.25rem' }}>
                    <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                      <div className="form-label">Accuracy & Wilson 95% CI</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>
                        {reportData.accuracy !== null && reportData.accuracy !== undefined ? `${(reportData.accuracy * 100).toFixed(1)}%` : 'None'}
                      </div>
                      {reportData.wilson_ci && (
                        <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
                          CI: [{(reportData.wilson_ci[0] * 100).toFixed(1)}%, {(reportData.wilson_ci[1] * 100).toFixed(1)}%]
                        </div>
                      )}
                    </div>

                    <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                      <div className="form-label">Latency p95 Percentile</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>
                        {reportData.latency_p95_ms ? `${reportData.latency_p95_ms.toFixed(1)} ms` : 'None'}
                      </div>
                      <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
                        p50: {reportData.latency_p50_ms ? `${reportData.latency_p50_ms.toFixed(0)}ms` : '-'} | p99: {reportData.latency_p99_ms ? `${reportData.latency_p99_ms.toFixed(0)}ms` : '-'}
                      </div>
                    </div>

                    <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                      <div className="form-label">Cohen's Kappa Agreement</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>
                        {reportData.cohen_kappa !== null && reportData.cohen_kappa !== undefined ? reportData.cohen_kappa.toFixed(3) : 'N/A'}
                      </div>
                      <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
                        Inter-rater / Ground truth
                      </div>
                    </div>

                    <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                      <div className="form-label">Cost per 1k Inferences</div>
                      <div style={{ fontSize: '1.25rem', fontWeight: 700, fontFamily: 'monospace' }}>
                        ${reportData.cost_per_1k_cases_usd.toFixed(4)}
                      </div>
                      <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
                        Total: ${reportData.total_cost_usd.toFixed(4)}
                      </div>
                    </div>
                  </div>

                  {/* Confusion Matrix if present */}
                  {reportData.confusion_matrix && (
                    <div style={{ marginBottom: '1.25rem' }}>
                      <div className="form-label">Confusion Matrix (Ground Truth vs Prediction)</div>
                      <div className="table-wrapper" style={{ maxWidth: 600 }}>
                        <table className="table">
                          <thead>
                            <tr>
                              <th>True \ Pred</th>
                              {reportData.confusion_matrix.labels.map((l) => (
                                <th key={l}>{l}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {reportData.confusion_matrix.matrix.map((row, i) => (
                              <tr key={i}>
                                <td><strong>{reportData.confusion_matrix?.labels[i]}</strong></td>
                                {row.map((val, j) => (
                                  <td
                                    key={j}
                                    style={{
                                      background: i === j && val > 0 ? 'rgba(52, 211, 153, 0.15)' : 'transparent',
                                      fontWeight: i === j ? 700 : 400,
                                    }}
                                  >
                                    {val}
                                  </td>
                                ))}
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Classification Report if present */}
                  {reportData.classification_report && Object.keys(reportData.classification_report).length > 0 && (
                    <div>
                      <div className="form-label">Per-Class Precision, Recall, and F1</div>
                      <div className="table-wrapper">
                        <table className="table">
                          <thead>
                            <tr>
                              <th>Class Label</th>
                              <th>Precision</th>
                              <th>Recall</th>
                              <th>F1 Score</th>
                              <th>Support</th>
                            </tr>
                          </thead>
                          <tbody>
                            {Object.entries(reportData.classification_report).map(([lbl, m]) => (
                              <tr key={lbl}>
                                <td><strong>{lbl}</strong></td>
                                <td>{m.precision !== null ? (m.precision * 100).toFixed(1) + '%' : 'None'}</td>
                                <td>{m.recall !== null ? (m.recall * 100).toFixed(1) + '%' : 'None'}</td>
                                <td>{m.f1 !== null ? (m.f1 * 100).toFixed(1) + '%' : 'None'}</td>
                                <td>{m.support}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {/* ----------------- SCREEN 10: BUDGET & LEDGER ----------------- */}
        {activeTab === 'budget' && budget && (
          <div>
            {budget.unresolved_count > 0 && (
              <div
                className="card"
                style={{
                  background: 'rgba(248, 113, 113, 0.15)',
                  borderColor: 'var(--accent-red)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                  <AlertTriangle size={22} color="var(--accent-red)" />
                  <div>
                    <div style={{ fontWeight: 700, color: 'var(--accent-red)' }}>
                      Execution Blocked: {budget.unresolved_count} Unresolved Transaction(s)
                    </div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      Under Invariant 4, unresolved transactions block all subsequent live runs fail-closed until reconciled.
                    </div>
                  </div>
                </div>
                <button
                  className="btn btn-danger"
                  onClick={() => {
                    if (budget.unresolved_transactions.length > 0) {
                      setReconcileTxId(budget.unresolved_transactions[0].transaction_id)
                    }
                    setShowReconcileModal(true)
                  }}
                >
                  Reconcile Transaction
                </button>
              </div>
            )}

            <div className="card">
              <div className="card-title">
                <Wallet size={18} color="var(--accent-blue)" />
                Spend Accounting Ledger & Balances
              </div>
              <div className="card-subtitle">
                Immutable SQLite WAL spend ledger with strictly typed provenance vocabulary (ACTUAL, ESTIMATED, UNRESOLVED, UNAVAILABLE).
              </div>

              <div className="grid-4" style={{ marginBottom: '1.25rem' }}>
                <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Total Spent USD</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 700 }}>${budget.spend.total_spent_usd.toFixed(4)}</div>
                  <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>Cap: ${budget.policy.total_budget_usd.toFixed(2)}</div>
                </div>

                <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Remaining Balance</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--accent-green)' }}>
                    ${budget.spend.remaining_total_usd.toFixed(4)}
                  </div>
                  <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>Available for live execution</div>
                </div>

                <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Pilot Spent USD</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 700 }}>${budget.spend.pilot_spent_usd.toFixed(4)}</div>
                  <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>Cap: ${budget.policy.pilot_budget_usd.toFixed(2)}</div>
                </div>

                <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, border: '1px solid var(--border-color)' }}>
                  <div className="form-label">Unresolved Entries</div>
                  <div style={{ fontSize: '1.35rem', fontWeight: 700, color: budget.unresolved_count > 0 ? 'var(--accent-red)' : 'var(--accent-green)' }}>
                    {budget.unresolved_count}
                  </div>
                  <div style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>Blocking live runs if &gt; 0</div>
                </div>
              </div>

              <div className="form-label" style={{ marginBottom: '0.5rem' }}>Recent Append-Only Transactions</div>
              <div className="table-wrapper">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Transaction ID</th>
                      <th>Timestamp</th>
                      <th>Model / Provider</th>
                      <th>Amount USD</th>
                      <th>Cost Basis</th>
                      <th>Unresolved</th>
                    </tr>
                  </thead>
                  <tbody>
                    {budget.recent_transactions.map((tx) => (
                      <tr key={tx.transaction_id}>
                        <td style={{ fontFamily: 'monospace', fontSize: '0.75rem' }}>{tx.transaction_id.slice(0, 16)}...</td>
                        <td>{tx.timestamp.slice(0, 19).replace('T', ' ')}</td>
                        <td>{tx.model_id} ({tx.provider})</td>
                        <td style={{ fontFamily: 'monospace' }}>${parseFloat(tx.amount_usd).toFixed(4)}</td>
                        <td>
                          <span className="badge badge-info">{tx.cost_basis}</span>
                        </td>
                        <td>
                          {tx.is_unresolved ? (
                            <span className="badge badge-danger">UNRESOLVED</span>
                          ) : (
                            <span className="badge badge-success">SETTLED</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* ----------------- SINGLE-USE LIVE APPROVAL MODAL ----------------- */}
      {showApprovalModal && planData && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: 'var(--accent-red)' }}>
              <AlertTriangle size={20} />
              <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>Authorize Live Benchmark Execution</div>
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              You are about to execute live API calls under fail-closed budget caps. This action will incur real financial charges.
            </div>

            <div style={{ background: 'var(--bg-input)', padding: '0.85rem', borderRadius: 6, marginBottom: '1rem', border: '1px solid var(--border-color)', fontSize: '0.8rem' }}>
              <div>Plan Fingerprint: <strong style={{ color: 'var(--accent-blue)', fontFamily: 'monospace' }}>{planData.plan_fingerprint}</strong></div>
              <div>Projected Cases: <strong>{planData.projected_cases}</strong></div>
              <div>Projected Max Spend: <strong>${planData.projected_cost_usd.toFixed(4)}</strong></div>
            </div>

            <div className="form-group">
              <label className="form-label">Authorized Operator Identity</label>
              <input
                type="text"
                className="input"
                value={approvalUser}
                onChange={(e) => setApprovalUser(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.25rem' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setShowApprovalModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-danger"
                onClick={handleExecuteLive}
                disabled={!approvalUser.trim()}
              >
                Issue Single-Use Token & Execute
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ----------------- BUDGET RECONCILE MODAL ----------------- */}
      {showReconcileModal && (
        <div className="modal-overlay">
          <div className="modal-content">
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem', color: 'var(--accent-amber)' }}>
              <Wallet size={20} />
              <div style={{ fontWeight: 700, fontSize: '1.1rem' }}>Reconcile Unresolved Transaction</div>
            </div>
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '1rem' }}>
              Assign a verified dollar amount to unblock live benchmark execution in the ledger.
            </div>

            <div className="form-group">
              <label className="form-label">Transaction ID</label>
              <input
                type="text"
                className="input"
                value={reconcileTxId}
                onChange={(e) => setReconcileTxId(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Reconciled USD Amount</label>
              <input
                type="number"
                step="0.0001"
                className="input"
                value={reconcileAmount}
                onChange={(e) => setReconcileAmount(e.target.value)}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Audit Note</label>
              <textarea
                className="textarea"
                rows={2}
                value={reconcileNotes}
                onChange={(e) => setReconcileNotes(e.target.value)}
              />
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.25rem' }}>
              <button
                className="btn btn-secondary"
                onClick={() => setShowReconcileModal(false)}
              >
                Cancel
              </button>
              <button
                className="btn btn-primary"
                onClick={handleReconcileSubmit}
                disabled={!reconcileTxId.trim()}
              >
                Confirm Reconciliation
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
