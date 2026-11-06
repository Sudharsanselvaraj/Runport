# Public SDK API Contract Specification (Python & TypeScript)

> **Status**: Approved Architectural Standard  
> **Target Release**: v0.3.0 Client Libraries → v1.0.0 General Availability  
> **Document Ref**: `RUNPORT-SPEC-003`  
> **Author**: Runport Architecture & Engineering Team  

---

## 1. Executive Summary

Runport v0.1.0 exposes execution capabilities through Typer CLI commands and an internal FastAPI service consumed by the React web dashboard. External automation currently requires either invoking subprocesses (`uv run runport ...`) or making unvalidated HTTP requests against undocumented REST routes.

This specification defines the public, typed client SDK contracts for **Python** (`runport`) and **TypeScript** (`@runport/sdk`). Both SDKs provide:
- Idiomatic synchronous and asynchronous client interfaces.
- Strict typing mapped directly from Pydantic v2 schemas and OpenAPI 3.1 definitions.
- Automatic plan fingerprint verification and budget preflight handling.
- Connection pooling, exponential backoff with jitter, and SSE event streaming.
- Comprehensive exception hierarchies reflecting fail-closed spend boundaries.

---

## 2. Python SDK Contract (`runport`)

### 2.1. Module Hierarchy
```text
runport/
├── __init__.py           # Exports Client, AsyncClient, and Core Models
├── client.py             # Sync Runport Client
├── async_client.py       # Async Runport Client
├── exceptions.py         # Exception Hierarchy
├── models/               # Pydantic v2 API Schemas
│   ├── benchmark.py
│   ├── budget.py
│   ├── dataset.py
│   ├── run.py
│   └── trace.py
└── resources/            # Domain Resource Managers
    ├── benchmarks.py
    ├── budget.py
    ├── datasets.py
    ├── runs.py
    └── traces.py
```

### 2.2. Client Initialization & Configuration
```python
from runport import Client, AsyncClient

# Synchronous Client
client = Client(
    base_url="http://127.0.0.1:8000",
    api_key="rp_live_abc123...",       # Optional for local, required for multi-tenant
    timeout=30.0,
    max_retries=3,
)

# Asynchronous Client
async_client = AsyncClient(
    base_url="http://127.0.0.1:8000",
    api_key="rp_live_abc123...",
)
```

### 2.3. Exception Hierarchy
```python
class RunportError(Exception):
    """Base exception for all Runport client errors."""
    pass

class AuthenticationError(RunportError):
    """Raised on 401 Unauthorized or invalid API key."""
    pass

class ValidationError(RunportError):
    """Raised on 422 Unprocessable Entity or invalid schema."""
    pass

class BudgetExceededError(RunportError):
    """Raised when an execution breaches spend cap without approval."""
    def __init__(self, message: str, fingerprint: str, estimated_usd: float, cap_usd: float):
        super().__init__(message)
        self.fingerprint = fingerprint
        self.estimated_usd = estimated_usd
        self.cap_usd = cap_usd

class ApprovalRequiredError(RunportError):
    """Raised when plan requires explicit human approval token."""
    def __init__(self, fingerprint: str, required_cap_usd: float):
        super().__init__(f"Plan {fingerprint} requires approval.")
        self.fingerprint = fingerprint
        self.required_cap_usd = required_cap_usd
```

### 2.4. Python Usage Example: Full Lifecycle
```python
import asyncio
from runport import AsyncClient, BudgetExceededError

async def main():
    async with AsyncClient() as client:
        # 1. Validate and upload evaluation dataset
        dataset = await client.datasets.upload(
            file_path="data/classification_dev.jsonl",
            name="customer_intent_v1",
        )
        print(f"Dataset uploaded: {dataset.id} (SHA256: {dataset.sha256})")

        # 2. Generate execution plan with preflight budget
        try:
            plan = await client.benchmarks.create_plan(
                candidate_models=["openrouter/anthropic/claude-3.5-sonnet", "ollama/llama3.2:latest"],
                dataset_id=dataset.id,
                prompt_template="Classify the intent of: {text}",
                budget_cap_usd=5.00,
            )
            print(f"Plan created: {plan.fingerprint} (Est: ${plan.estimated_cost_usd:.4f})")
            
            # 3. Execute plan
            run = await client.runs.execute(plan.fingerprint)
            
        except BudgetExceededError as e:
            print(f"Budget cap exceeded! Estimated: ${e.estimated_usd}, Cap: ${e.cap_usd}")
            # Request approval override
            approval = await client.budget.approve(
                fingerprint=e.fingerprint,
                max_spend_usd=10.00,
            )
            run = await client.runs.execute(
                fingerprint=e.fingerprint,
                approval_token=approval.token,
            )

        # 4. Stream real-time progress events
        async for event in client.runs.stream_events(run.id):
            print(f"[{event.timestamp}] Step {event.completed}/{event.total}: {event.message}")

        # 5. Fetch final evaluation metrics
        summary = await client.runs.get_summary(run.id)
        print(f"Run completed in {summary.duration_seconds:.2f}s")
        print(f"Accuracy: {summary.metrics['accuracy']:.3f} | Booked Spend: ${summary.total_spend_usd:.4f}")

asyncio.run(main())
```

---

## 3. TypeScript SDK Contract (`@runport/sdk`)

### 3.1. Package Structure
```text
packages/sdk-ts/
├── package.json          # "@runport/sdk"
├── tsconfig.json
├── src/
│   ├── index.ts          # Main package export
│   ├── client.ts         # RunportClient implementation
│   ├── errors.ts         # Typed Error classes
│   ├── types.ts          # API request and response interfaces
│   └── resources/
│       ├── benchmarks.ts
│       ├── budget.ts
│       ├── datasets.ts
│       ├── runs.ts
│       └── traces.ts
└── tests/
    └── client.test.ts
```

### 3.2. TypeScript API Definitions
```typescript
export interface RunportConfig {
  baseUrl?: string;         // Defaults to "http://127.0.0.1:8000"
  apiKey?: string;          // Optional for localhost
  timeoutMs?: number;       // Defaults to 30000ms
  fetchFn?: typeof fetch;   // Custom fetch implementation
}

export interface ExecutionPlan {
  planId: string;
  fingerprint: string;
  candidateModels: string[];
  datasetSha256: string;
  promptTemplateSha256: string;
  estimatedCostUsd: number;
  budgetCapUsd: number;
  approvalRequired: boolean;
}

export interface RunProgressEvent {
  runId: string;
  completed: number;
  total: number;
  currentModel: string;
  currentCostUsd: number;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

export interface BenchmarkMetrics {
  accuracy?: number;
  f1Score?: number;
  precision?: number;
  recall?: number;
  wilsonCiLower?: number;
  wilsonCiUpper?: number;
  cohensKappa?: number;
}
```

### 3.3. TypeScript Usage Example
```typescript
import { RunportClient, BudgetExceededError } from '@runport/sdk';

const client = new RunportClient({
  baseUrl: 'http://127.0.0.1:8000',
  apiKey: process.env.RUNPORT_API_KEY,
});

async function runBenchmark() {
  try {
    // 1. Create plan
    const plan = await client.benchmarks.createPlan({
      candidateModels: ['openrouter/google/gemini-2.0-flash-001'],
      datasetId: 'dataset-123',
      promptTemplate: 'Extract entities from: {{text}}',
      budgetCapUsd: 2.00,
    });

    console.log(`Plan generated: ${plan.fingerprint}`);

    // 2. Execute plan
    const run = await client.runs.execute({
      planFingerprint: plan.fingerprint,
    });

    // 3. Listen to SSE live events
    const subscription = client.runs.subscribeEvents(run.id, (event) => {
      console.log(`Progress: ${event.completed} / ${event.total} items evaluated`);
    });

    await subscription.untilComplete();

    // 4. Retrieve metrics
    const results = await client.runs.getResults(run.id);
    console.log('Run Complete:', results.metrics);
  } catch (error) {
    if (error instanceof BudgetExceededError) {
      console.error(`Spend cap exceeded: requires $${error.estimatedUsd}`);
    } else {
      console.error('Benchmark failed:', error);
    }
  }
}

runBenchmark();
```

---

## 4. Error Handling & Transport Resiliency

Both client SDKs enforce bounded retry policies:
- **Retryable Status Codes**: HTTP 429 (Rate Limit), 502 (Bad Gateway), 503 (Service Unavailable), 504 (Gateway Timeout).
- **Non-Retryable Status Codes**: HTTP 400 (Bad Request), 401 (Unauthorized), 402 (Budget Exceeded), 404 (Not Found), 422 (Validation Error).
- **Backoff Algorithm**:
  $$t_{\text{wait}} = \min(t_{\text{max}},\, t_{\text{base}} \times 2^{\text{attempt}}) \pm \text{jitter}$$
- **Fail-Closed Budget**: HTTP 402 responses are immediately translated into `BudgetExceededError` without retrying.

