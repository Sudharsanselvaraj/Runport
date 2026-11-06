---
title: Benchmark an existing project
description: The ways to benchmark an agent, workflow or model you already have, from least to most effort, with their limits.
---

Every path below ends in the same place: a fingerprinted plan, approval by a person (or automatic approval when every target runs
locally), and execution through `GenericRunner` with the budget, privacy and ledger rules. Pick the first one that fits.

## 1. A Python function (no changes to your code)

```python
from runport.sdk import benchmark
from my_app import answer          # your existing function: case dict in, text or dict out

result = benchmark(answer, "data/evaluation/cases.jsonl")
print(result.runs[0].successful_cases, result.runs[0].mean_latency_ms)
```

A function runs in-process, so the plan is approved automatically (nothing can leave the machine through Runport, and nothing is
billed through it). **Limit:** if your function itself calls a paid API, Runport cannot see that spend; it records the cost as
`UNAVAILABLE`. Declare such code as an HTTP endpoint or wrap it in a target with `billing=BillingMode.BILLABLE` and pricing.

## 2. An HTTP endpoint (any language)

Declare the endpoint once in `runport.yaml`:

```yaml
targets:
  - id: support-agent
    type: http_workflow
    endpoint: https://agent.example.com/chat
    headers:
      Authorization: Bearer ${SUPPORT_AGENT_TOKEN}
    options:
      output_path: reply
      payload_template:
        message: "{{query}}"
      pricing:                       # optional
        fixed_usd_per_request: "0.002"
```

Use block style as above: without PyYAML installed, Runport's built-in YAML reader does not understand inline `{...}` maps.

Then `runport benchmark --target support-agent --dataset data/evaluation/cases.jsonl --split ALL --live`, or select it on the
dashboard's Plan page. A loopback endpoint (`http://127.0.0.1:...`, with `allow_localhost: true` in `options`) is local; any other
host is billable unless you add `billing: unbilled` to `options`. **Limits:** black box only (no internal steps), tokens only if the
response has a `usage` object, cost only with `pricing`; otherwise each case is booked `UNRESOLVED` and the run stops after the first.

## 3. An OpenAI-compatible server

Point `type: openai_compat` at the server's `/v1` base URL (vLLM, LM Studio, LocalAI, a LiteLLM proxy, Groq, Together and so on).
**Limits:** chat completions only, no streaming, cost only with `pricing`.

## 4. An MCP server's tools

`type: mcp` with `command:` (stdio) or `endpoint:` (Streamable HTTP). See [MCP](/mcp). **Limit:** this benchmarks the tools, not
the agent that would choose them.

## 5. From a coding agent

Run `runport mcp serve` and let the agent plan and execute; you approve with `runport approve <plan_id>`. See [MCP](/mcp).

## 6. In CI

```python
from runport.sdk import plan, approve_with_ci_token, execute

p = plan("support-agent", "data/evaluation/cases.jsonl")
approve_with_ci_token(p, token=p.fingerprint)   # requires approver.token_approver_enabled: true in runport.yaml
outcome = execute(p)
assert outcome.runs[0].halted_reason is None
```

Enable the token approver only in CI jobs whose budget ceilings you accept, since the job approves its own plan. **Limits:** there
are no regression thresholds or PR comments yet; assert on the run results yourself.

## Not available yet

- An OpenAI-compatible **proxy** that records your app's model calls without code changes.
- Framework callbacks (LangChain, LangGraph, CrewAI, LlamaIndex): use paths 1 or 2 today.
- OpenTelemetry / OpenInference trace ingestion: `runport import-traces` reads Langfuse-style JSON and CSV only.
- Per-step agent trajectories in results (only Dify workflow node data is captured, as metadata).
