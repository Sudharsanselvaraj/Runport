/**
 * Runport TypeScript SDK Domain and API v1 Types.
 *
 * Invariant: Null is not 0. Missing telemetry remains null or undefined, never fabricated to zero.
 */

export interface RunportConfig {
  /** Base URL of the Runport daemon (defaults to "http://127.0.0.1:8000") */
  baseUrl?: string;
  /** Bearer API token with required operation scopes */
  apiKey?: string;
  /** Optional project ID for multi-tenant isolation */
  projectId?: string;
  /** Request timeout in milliseconds (defaults to 30000ms) */
  timeoutMs?: number;
  /** Optional custom fetch implementation (useful for tests and edge runtimes) */
  fetch?: typeof globalThis.fetch;
}

export interface TargetItem {
  target_id: string;
  name: string;
  target_type: string;
  provider: string;
  license?: string | null;
  context_length?: number | null;
  input_price_per_1m_usd?: number | null;
  output_price_per_1m_usd?: number | null;
  verification_status?: string | null;
  billing: 'local' | 'metered' | 'subscription' | 'unpriced' | string;
}

export interface DatasetItem {
  filename: string;
  size_bytes: number;
  case_count: number;
  path?: string | null;
  message?: string | null;
}

export interface EvaluationCase {
  id: string;
  query: string;
  expected_answer?: string | null;
  classification?: 'PUBLIC' | 'SYNTHETIC' | 'INTERNAL' | 'CONFIDENTIAL' | 'RESTRICTED' | string;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface TargetPlanCost {
  target_id: string;
  type: string;
  billing: string;
  priced: boolean;
  projected_cost_usd?: string | null;
  pricing_rule?: string | null;
}

export interface Plan {
  plan_id: string;
  plan_fingerprint: string;
  status: 'PENDING' | 'APPROVED' | 'CONSUMED' | 'EXPIRED' | string;
  expires_at: number;
  target_ids: string[];
  case_count: number;
  dataset_label: string;
  projected_max_cost_usd?: string | null;
  per_target: TargetPlanCost[];
  blockers: string[];
  confirmation_phrase: string;
  requested_by: string;
  approved_by?: string | null;
}

export interface PlanCreateOptions {
  targetIds: string[];
  datasetName: string;
  sampleSize?: number;
  isPilot?: boolean;
}

export interface PlanApproveOptions {
  planId: string;
  fingerprint: string;
  approver?: string;
}

export interface Job {
  job_id: string;
  plan_id: string;
  run_id?: string | null;
  status: 'queued' | 'running' | 'completed' | 'failed' | 'cancelled' | string;
  total_cases: number;
  completed_cases: number;
  failed_cases: number;
  booked_spend_usd?: string | null;
  error_message?: string | null;
  cancelled: boolean;
  idempotency_key?: string | null;
  created_at: string;
  updated_at: string;
  finished_at?: string | null;
}

export interface RunSubmitOptions {
  planId: string;
  sampleSize?: number;
  idempotencyKey?: string;
}

export interface RunDetail {
  run_id: string;
  timestamp: string;
  model_id: string;
  dataset_path: string;
  total_cases: number;
  completed_cases: number;
  failed_cases: number;
  total_cost_usd: string;
  mean_latency_ms?: number | null;
  mean_accuracy?: number | null;
  mean_groundedness?: number | null;
  mean_overall_score?: number | null;
  is_dry_run: boolean;
  notes?: string | null;
}

export interface RunResultItem {
  result_id?: string | null;
  case_id: string;
  prompt: string;
  generated_output?: string | null;
  latency_ms?: number | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  cost_usd?: string | null;
  cost_basis?: 'ACTUAL' | 'ESTIMATED' | 'UNRESOLVED' | 'UNAVAILABLE' | string | null;
  accuracy?: number | null;
  score_kind?: string | null;
  trace_id?: string | null;
}

export interface BudgetPolicyInfo {
  total_budget_usd: number;
  pilot_budget_usd: number;
  per_run_ceiling_usd: number;
  per_case_ceiling_usd: number;
  require_priced: boolean;
}

export interface BudgetSpendInfo {
  total_spent_usd: number;
  pilot_spent_usd: number;
  remaining_total_usd: number;
  remaining_pilot_usd: number;
}

export interface BudgetStatus {
  policy: BudgetPolicyInfo;
  spend: BudgetSpendInfo;
  unresolved_count: number;
  unresolved_transactions: Array<Record<string, unknown>>;
  unresolved_blocked: boolean;
}

export interface TraceSpan {
  span_id: string;
  trace_id: string;
  parent_span_id?: string | null;
  name: string;
  kind: 'internal' | 'server' | 'client' | 'producer' | 'consumer' | string;
  start_time: string;
  end_time?: string | null;
  status: 'unset' | 'ok' | 'error' | string;
  status_message?: string | null;
  attributes: Record<string, unknown>;
  events: Array<{
    name: string;
    timestamp: string;
    attributes?: Record<string, unknown>;
  }>;
}

export interface CanonicalTrace {
  trace_id: string;
  root_span_id: string;
  run_id?: string | null;
  case_id?: string | null;
  target_id?: string | null;
  status: string;
  spans: TraceSpan[];
}
