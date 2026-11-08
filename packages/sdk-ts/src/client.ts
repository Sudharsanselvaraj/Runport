/**
 * Runport TypeScript Client.
 *
 * Provides typed access to Runport's REST API v1.
 * Works seamlessly in Node.js, modern browsers, Bun, and Deno via isomorphic fetch.
 */

import { createRunportError, RunportError } from './errors.js';
import type {
  BudgetStatus,
  CanonicalTrace,
  DatasetItem,
  EvaluationCase,
  Job,
  Plan,
  PlanApproveOptions,
  PlanCreateOptions,
  RunDetail,
  RunportConfig,
  RunResultItem,
  RunSubmitOptions,
  TargetItem,
} from './types.js';

export class RunportClient {
  readonly baseUrl: string;
  readonly apiKey?: string;
  readonly timeoutMs: number;
  private readonly fetchImpl: typeof globalThis.fetch;

  constructor(config: RunportConfig = {}) {
    this.baseUrl = (config.baseUrl ?? 'http://127.0.0.1:8000').replace(/\/+$/, '');
    this.apiKey = config.apiKey;
    this.timeoutMs = config.timeoutMs ?? 30000;
    this.fetchImpl = config.fetch ?? globalThis.fetch.bind(globalThis);
  }

  private async request<T>(method: string, path: string, body?: unknown, params?: Record<string, string | number | undefined>): Promise<T> {
    const url = new URL(`${this.baseUrl}/api/v1${path}`);
    if (params) {
      for (const [key, val] of Object.entries(params)) {
        if (val !== undefined) {
          url.searchParams.append(key, String(val));
        }
      }
    }

    const headers: Record<string, string> = {
      Accept: 'application/json',
    };
    if (this.apiKey) {
      headers['Authorization'] = `Bearer ${this.apiKey}`;
    }
    if (body !== undefined && !(body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);

    let res: Response;
    try {
      res = await this.fetchImpl(url.toString(), {
        method,
        headers,
        body: body !== undefined ? (body instanceof FormData ? body : JSON.stringify(body)) : undefined,
        signal: controller.signal,
      });
    } catch (err: unknown) {
      clearTimeout(timer);
      if (err instanceof Error && err.name === 'AbortError') {
        throw new RunportError('timeout', `Request to ${url.pathname} timed out after ${this.timeoutMs}ms`, 408);
      }
      throw new RunportError('network_error', `Failed to fetch ${url.toString()}: ${(err as Error).message}`, 503);
    } finally {
      clearTimeout(timer);
    }

    if (!res.ok) {
      let errPayload: unknown;
      try {
        errPayload = await res.json();
      } catch {
        errPayload = null;
      }
      throw createRunportError(res.status, errPayload);
    }

    return (await res.json()) as T;
  }

  // =========================================================================
  // Targets Resource
  // =========================================================================

  readonly targets = {
    list: async (): Promise<TargetItem[]> => {
      return this.request<TargetItem[]>('GET', '/targets');
    },
    get: async (targetId: string): Promise<TargetItem> => {
      return this.request<TargetItem>('GET', `/targets/${encodeURIComponent(targetId)}`);
    },
  };

  // =========================================================================
  // Datasets Resource
  // =========================================================================

  readonly datasets = {
    list: async (): Promise<DatasetItem[]> => {
      return this.request<DatasetItem[]>('GET', '/datasets');
    },
    get: async (name: string): Promise<DatasetItem> => {
      return this.request<DatasetItem>('GET', `/datasets/${encodeURIComponent(name)}`);
    },
    upload: async (name: string, cases: EvaluationCase[]): Promise<DatasetItem> => {
      const jsonl = cases.map((c) => JSON.stringify(c)).join('\n') + '\n';
      const form = new FormData();
      const blob = new Blob([jsonl], { type: 'application/json' });
      form.append('file', blob, name);
      return this.request<DatasetItem>('POST', '/datasets', form);
    },
  };

  // =========================================================================
  // Plans & Approvals Resource
  // =========================================================================

  readonly plans = {
    create: async (opts: PlanCreateOptions): Promise<Plan> => {
      return this.request<Plan>('POST', '/plans', {
        target_ids: opts.targetIds,
        dataset_name: opts.datasetName,
        sample_size: opts.sampleSize,
        is_pilot: opts.isPilot ?? false,
      });
    },
    get: async (planId: string): Promise<Plan> => {
      return this.request<Plan>('GET', `/plans/${encodeURIComponent(planId)}`);
    },
    approve: async (opts: PlanApproveOptions): Promise<Plan> => {
      return this.request<Plan>('POST', `/plans/${encodeURIComponent(opts.planId)}/approve`, {
        fingerprint: opts.fingerprint,
        approver: opts.approver ?? 'operator',
      });
    },
  };

  // =========================================================================
  // Asynchronous Jobs Resource
  // =========================================================================

  readonly jobs = {
    submit: async (opts: RunSubmitOptions): Promise<Job> => {
      return this.request<Job>('POST', `/plans/${encodeURIComponent(opts.planId)}/runs`, {
        sample_size: opts.sampleSize,
        idempotency_key: opts.idempotencyKey,
      });
    },
    get: async (jobId: string): Promise<Job> => {
      return this.request<Job>('GET', `/jobs/${encodeURIComponent(jobId)}`);
    },
    cancel: async (jobId: string): Promise<Job> => {
      return this.request<Job>('POST', `/jobs/${encodeURIComponent(jobId)}/cancel`);
    },
    wait: async (jobId: string, opts?: { timeoutMs?: number; pollIntervalMs?: number }): Promise<Job> => {
      const timeout = opts?.timeoutMs ?? 300000;
      const interval = opts?.pollIntervalMs ?? 500;
      const start = Date.now();

      while (true) {
        const job = await this.jobs.get(jobId);
        if (['completed', 'failed', 'cancelled'].includes(job.status)) {
          return job;
        }
        if (Date.now() - start > timeout) {
          throw new RunportError('timeout', `Job ${jobId} did not finish within ${timeout}ms`, 408);
        }
        await new Promise((r) => setTimeout(r, interval));
      }
    },
  };

  // =========================================================================
  // Runs, Results & Traces Resource
  // =========================================================================

  readonly runs = {
    list: async (limit = 50): Promise<RunDetail[]> => {
      return this.request<RunDetail[]>('GET', '/runs', undefined, { limit });
    },
    get: async (runId: string): Promise<RunDetail> => {
      return this.request<RunDetail>('GET', `/runs/${encodeURIComponent(runId)}`);
    },
    getResults: async (runId: string, opts?: { limit?: number; offset?: number }): Promise<{ run_id: string; total_cases: number; results: RunResultItem[] }> => {
      return this.request('GET', `/runs/${encodeURIComponent(runId)}/results`, undefined, {
        limit: opts?.limit ?? 100,
        offset: opts?.offset ?? 0,
      });
    },
  };

  readonly traces = {
    get: async (caseId: string, runId?: string): Promise<CanonicalTrace> => {
      return this.request<CanonicalTrace>('GET', `/traces/${encodeURIComponent(caseId)}`, undefined, { run_id: runId });
    },
    submit: async (tracePayload: unknown): Promise<{ message: string; trace_id: string; span_count: number }> => {
      return this.request('POST', '/traces', tracePayload);
    },
  };

  // =========================================================================
  // Budget Governance Resource
  // =========================================================================

  readonly budget = {
    get: async (): Promise<BudgetStatus> => {
      const data = await this.request<any>('GET', '/budget');
      return {
        ...data,
        unresolved_blocked: (data.unresolved_count ?? 0) > 0,
      };
    },
    reconcile: async (transactionId: string, reconciledUsd: number, notes = ''): Promise<{ message: string; transaction_id: string; status: string }> => {
      return this.request('POST', '/budget/reconcile', {
        transaction_id: transactionId,
        reconciled_usd: reconciledUsd,
        notes,
      });
    },
  };

  // =========================================================================
  // Root Level Conveniences
  // =========================================================================

  plan = this.plans.create;
  approve = this.plans.approve;
  execute = this.jobs.submit;
  wait = this.jobs.wait;
}
