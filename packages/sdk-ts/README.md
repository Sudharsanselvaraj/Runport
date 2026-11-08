# @runport/sdk

Official TypeScript / JavaScript client SDK for [Runport](https://github.com/Sudharsanselvaraj/Runport), the universal, local-first LLM and workflow benchmarking platform under hard spend caps.

## Features

- **Isomorphic**: Works identically in Node.js 18+, browsers, Bun, Deno, and edge runtimes via standard `fetch`.
- **Strict Invariants**: Enforces Runport's "Null is not 0" invariant — unmeasured telemetry is never fabricated to zero.
- **Fail-Closed Spend Protection**: Typed error handling for `BudgetExceededError`, `ApprovalRequiredError`, and `UnresolvedSpendError`.
- **Asynchronous Execution Model**: Submit plans for background execution and await completion with cooperative cancellation support.

## Installation

```bash
npm install @runport/sdk
```

## Quickstart

```typescript
import { RunportClient, ApprovalRequiredError } from '@runport/sdk';

const client = new RunportClient({
  baseUrl: 'http://127.0.0.1:8000',
  apiKey: process.env.RUNPORT_API_KEY,
});

async function main() {
  // 1. List available targets
  const targets = await client.targets.list();
  console.log(`Found ${targets.length} targets.`);

  // 2. Create a cost-checked benchmark plan (PENDING, sends zero live requests)
  const plan = await client.plans.create({
    targetIds: ['google/gemini-3.5-flash-lite'],
    datasetName: 'finance_qa.jsonl',
    sampleSize: 10,
  });

  console.log(`Plan ID: ${plan.plan_id}`);
  console.log(`Fingerprint: ${plan.plan_fingerprint}`);
  console.log(`Confirmation phrase: "${plan.confirmation_phrase}"`);

  // 3. Human authorization (explicit fingerprint confirmation)
  const approved = await client.plans.approve({
    planId: plan.plan_id,
    fingerprint: plan.plan_fingerprint,
    approver: 'operator',
  });

  // 4. Submit approved plan for asynchronous background execution
  const job = await client.jobs.submit({ planId: approved.plan_id });
  console.log(`Job queued with ID: ${job.job_id}`);

  // 5. Wait for completion
  const finished = await client.jobs.wait(job.job_id);
  console.log(`Job finished with status: ${finished.status}`);
}

main().catch(console.error);
```

## License

Apache-2.0
