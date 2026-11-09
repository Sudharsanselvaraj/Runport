/**
 * Offline unit tests for @runport/sdk (TypeScript client).
 *
 * Runs via `node --experimental-strip-types --test tests/client.test.ts`.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import {
  ApprovalRequiredError,
  BudgetExceededError,
  NotFoundError,
  PermissionDeniedError,
  RunportClient,
  RunportError,
} from '../dist/index.js';

describe('RunportClient', () => {
  it('creates client with configuration and defaults', () => {
    const client = new RunportClient({ baseUrl: 'http://localhost:9000/' });
    assert.equal(client.baseUrl, 'http://localhost:9000');
    assert.equal(client.timeoutMs, 30000);
  });

  it('lists targets via mock fetch', async () => {
    const mockFetch: typeof globalThis.fetch = async (input, init) => {
      const url = input.toString();
      assert.match(url, /\/api\/v1\/targets$/);
      assert.equal(init?.method, 'GET');

      return new Response(
        JSON.stringify([
          {
            target_id: 'google/gemini-3.5-flash-lite',
            name: 'Gemini 3.5 Flash Lite',
            target_type: 'model',
            provider: 'google',
            billing: 'metered',
          },
        ]),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      );
    };

    const client = new RunportClient({ fetch: mockFetch });
    const targets = await client.targets.list();
    assert.equal(targets.length, 1);
    assert.equal(targets[0].target_id, 'google/gemini-3.5-flash-lite');
  });

  it('creates and approves a plan and enforces typed error mapping', async () => {
    const mockFetch: typeof globalThis.fetch = async (input, init) => {
      const url = input.toString();

      if (url.includes('/api/v1/plans/plan-123/runs') && init?.method === 'POST') {
        return new Response(
          JSON.stringify({
            error: {
              code: 'approval_required',
              message: 'Plan has not been approved.',
              details: { plan_id: 'plan-123' },
            },
          }),
          { status: 428, headers: { 'Content-Type': 'application/json' } }
        );
      }

      if (url.includes('/api/v1/plans/plan-123/approve') && init?.method === 'POST') {
        return new Response(
          JSON.stringify({
            plan_id: 'plan-123',
            plan_fingerprint: 'sha256-abc',
            status: 'APPROVED',
            expires_at: 1700000000,
            target_ids: ['google/gemini-3.5-flash-lite'],
            case_count: 5,
            dataset_label: 'eval.jsonl',
            per_target: [],
            blockers: [],
            confirmation_phrase: 'RUN LIVE PLAN',
            requested_by: 'api',
            approved_by: 'operator:admin',
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        );
      }

      return new Response(JSON.stringify({ error: { code: 'not_found', message: 'Route not found' } }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    const client = new RunportClient({ fetch: mockFetch });

    // 1. Unapproved run fails with ApprovalRequiredError (428)
    await assert.rejects(
      async () => {
        await client.jobs.submit({ planId: 'plan-123' });
      },
      (err: unknown) => {
        assert(err instanceof ApprovalRequiredError);
        assert.equal(err.statusCode, 428);
        assert.equal(err.code, 'approval_required');
        return true;
      }
    );

    // 2. Approving plan returns approved Plan
    const approved = await client.plans.approve({
      planId: 'plan-123',
      fingerprint: 'sha256-abc',
      approver: 'admin',
    });
    assert.equal(approved.status, 'APPROVED');
    assert.equal(approved.approved_by, 'operator:admin');
  });

  it('maps budget_exceeded error envelope to BudgetExceededError', async () => {
    const mockFetch: typeof globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({
          error: {
            code: 'budget_exceeded',
            message: 'Spend cap of $5.00 exceeded.',
            details: { limit: 5.0, spent: 5.25 },
          },
        }),
        { status: 402, headers: { 'Content-Type': 'application/json' } }
      );
    };

    const client = new RunportClient({ fetch: mockFetch });
    await assert.rejects(
      async () => {
        await client.plans.create({
          targetIds: ['openai/gpt-4o'],
          datasetName: 'heavy.jsonl',
        });
      },
      (err: unknown) => {
        assert(err instanceof BudgetExceededError);
        assert.equal(err.statusCode, 402);
        assert.equal(err.code, 'budget_exceeded');
        return true;
      }
    );
  });

  it('propagates X-Project-Id and Idempotency-Key headers', async () => {
    let capturedHeaders: HeadersInit | undefined;
    const mockFetch: typeof globalThis.fetch = async (input, init) => {
      capturedHeaders = init?.headers;
      return new Response(
        JSON.stringify({
          job_id: 'job-idemp-1',
          plan_id: 'plan-123',
          status: 'queued',
          total_cases: 5,
          completed_cases: 0,
          failed_cases: 0,
          cancelled: false,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          idempotency_key: 'idemp-xyz-999',
        }),
        { status: 202, headers: { 'Content-Type': 'application/json' } }
      );
    };

    const client = new RunportClient({
      projectId: 'proj-finance',
      apiKey: 'secret-key-123',
      fetch: mockFetch,
    });

    const job = await client.jobs.submit({
      planId: 'plan-123',
      sampleSize: 5,
      idempotencyKey: 'idemp-xyz-999',
    });

    assert.equal(job.job_id, 'job-idemp-1');
    assert(capturedHeaders);
    const headersObj = capturedHeaders as Record<string, string>;
    assert.equal(headersObj['X-Project-Id'], 'proj-finance');
    assert.equal(headersObj['Idempotency-Key'], 'idemp-xyz-999');
    assert.equal(headersObj['Authorization'], 'Bearer secret-key-123');
  });
});
