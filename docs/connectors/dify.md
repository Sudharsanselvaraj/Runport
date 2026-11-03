# Dify Connector Specification

The `dify` connector benchmarks applications built on the [Dify](https://dify.ai) platform, supporting both **Chat Applications** and **Workflow Applications** under fail-closed budget caps.

---

## 1. Capabilities & Endpoint Routing

| Application Type | Endpoint Route | Modes Supported | Trace Telemetry |
|:---|:---|:---:|:---:|
| **Chat App** | `POST /v1/chat-messages` | `blocking`, `streaming` | `metadata.usage` (prompt/completion tokens), `conversation_id`, `message_id` |
| **Workflow App** | `POST /v1/workflows/run` | `blocking`, `streaming` | `data.total_tokens`, `data.total_steps`, `data.node_executions` (per-node trace) |

### Capabilities Declared
- Chat: `["streaming", "usage"]`
- Workflow: `["streaming", "usage", "per_step_trace"]`

---

## 2. Configuration Example (`runport.yaml`)

```yaml
targets:
  - id: "dify-customer-support-chat"
    type: "dify"
    endpoint: "https://api.dify.ai/v1"
    options:
      app_type: "chat"
      response_mode: "blocking"   # or "streaming"
      user: "eval-runner"
    headers:
      Authorization: "$DIFY_CHAT_APP_KEY"

  - id: "dify-document-extraction-workflow"
    type: "dify"
    endpoint: "https://api.dify.ai/v1"
    options:
      app_type: "workflow"
      response_mode: "streaming"
      user: "eval-runner"
    headers:
      Authorization: "$DIFY_WORKFLOW_APP_KEY"
```

---

## 3. Owner-Run Smoke-Test Procedure

> [!IMPORTANT]
> The automated test suite operates completely offline with blocked sockets and mock fixtures. To perform an authorized live smoke-test on your self-hosted or SaaS Dify instance, execute the following manual procedure:

### Prerequisites
1. Set your Dify Application API key in your shell environment:
   ```bash
   export DIFY_API_KEY="app-xxxxxxxxxxxxxxxx"
   ```
2. Verify network reachability to your Dify instance:
   ```bash
   curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: Bearer $DIFY_API_KEY" https://api.dify.ai/v1/parameters
   ```

### Step 1: Preflight Verification
Verify that your local spend ceilings and target configuration pass validation:
```bash
uv run runport api-preflight
```

### Step 2: Single-Case Smoke Test
Execute a pilot benchmark covering a synthetic evaluation case:
```bash
uv run python -c "
from runport.connectors.dify import DifyConnector
import os

key = os.environ.get('DIFY_API_KEY')
if not key:
    raise RuntimeError('DIFY_API_KEY environment variable not set')

target = DifyConnector(
    target_id='dify-smoke-test',
    name='Dify Chat App Smoke Test',
    api_key=key,
    base_url='https://api.dify.ai/v1',
    app_type='chat',
    response_mode='blocking'
)

result = target.execute({'query': 'Hello, what capabilities does this agent provide?'})
print('Status:', result.status)
print('Output:', result.output_text)
print('Tokens in:', result.tokens_in)
print('Tokens out:', result.tokens_out)
print('Latency:', result.latency_ms, 'ms')
"
```

### Step 3: Verify Output & Spend Ledger
Confirm that the transaction is recorded cleanly in the local ledger without unresolved entries:
```bash
uv run runport budget status
```
