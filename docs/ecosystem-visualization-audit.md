# Ecosystem visualization audit

Scope: the "Keep your stack. Runport benchmarks it." visualization on the public landing page
(`web/src/components/landing/BenchmarkFlow.tsx`, data in `web/src/data/ecosystem.ts`).

The rule for every entry: the landing page may only claim what the repository can back. A technology
with no dedicated connector is never drawn as a native integration.

## Status vocabulary

| Status | Meaning | Visual treatment |
| --- | --- | --- |
| Implemented (`native`) | A dedicated connector, adapter or module exists in `src/runport` | Solid chip |
| Experimental (`exp`) | A dedicated connector exists and is marked experimental in code | Solid chip with `EXP` badge |
| Ecosystem compatible (`compat`) | No dedicated connector; reached through a generic one | Dashed, dimmer chip with `↔`; tooltip names the route (`via …`) |
| Planned | Not built | Not shown |

## Entries and evidence

### Model providers

| Entry | Status | Evidence / route |
| --- | --- | --- |
| OpenAI | Implemented | `connectors/openai_compat.py` (default base URL api.openai.com) |
| OpenRouter | Implemented | `providers/openrouter.py` |
| Anthropic, Gemini, Mistral, Llama, DeepSeek | Compatible | Model IDs routed through OpenRouter; the default CLI model is `google/gemini-*` via OpenRouter |
| Groq, Together, Fireworks, DeepInfra | Compatible | OpenAI-compatible endpoints; `OpenAICompatConnector(base_url=…)` |

### Local inference

| Entry | Status | Evidence / route |
| --- | --- | --- |
| Ollama | Implemented | `connectors/ollama.py` |
| vLLM, LocalAI | Compatible | Named in the `connectors/openai_compat.py` docstring |
| LM Studio, HF TGI, LiteLLM proxy | Compatible | Serve an OpenAI-compatible API; reached with the OpenAI-compatible connector |

### Workflows & agents

| Entry | Status | Evidence / route |
| --- | --- | --- |
| Dify | Implemented | `connectors/dify.py` |
| LangGraph, Flowise, Langflow, n8n | Experimental | `connectors/langgraph.py`, `flowise.py`, `langflow.py`, `n8n.py` |
| LangChain, LlamaIndex, CrewAI | Compatible | Wrap `invoke` / `query` / `kickoff` in `PythonCallableTarget` |

### Evaluation & scoring

| Entry | Status | Evidence / route |
| --- | --- | --- |
| Exact & regex, Classification, Extraction, Generation | Implemented | `scorers/match.py`, `scorers/classification.py`, `scorers/extraction.py`, `scorers/generation.py` |
| RAG metrics | Implemented | `rag/evaluator.py` |
| LLM judge | Implemented | `scorers/llm_judge.py` (user-supplied judge function) |
| DeepEval, Ragas | Compatible | Wrap a metric as a `runport.scorers` entry point (`core/plugins.py`); the repo contains no code for either |

### Data & traces

| Entry | Status | Evidence / route |
| --- | --- | --- |
| JSONL datasets | Implemented | `schemas/evaluation.py`, `runport validate-dataset` |
| SQLite WAL | Implemented | `storage/db.py` |
| BM25 retriever | Implemented | `rag/retriever.py` |
| Trace export | Implemented | `runport export-traces` (JSONL, CSV, ZIP) |
| Langfuse | Implemented | `runport import-traces` reads Langfuse JSON/CSV exports |
| Helicone | Compatible | Gateway `base_url` plus `custom_headers` on the OpenAI-compatible connector |

### Execution & infra

| Entry | Status | Evidence / route |
| --- | --- | --- |
| HTTP endpoint | Implemented | `connectors/http_workflow.py` |
| Python callable, Subprocess | Implemented | `connectors/python_target.py` |
| Replay | Implemented | `runs/replay.py` |
| Plugins | Implemented | `core/plugins.py` entry points |
| Docker | Implemented | `Dockerfile` (multi-stage) |
| GitHub Actions | Compatible | `.github/workflows/ci.yml` exists; replay runs need no API key, so a benchmark replay can run in CI. There is no dedicated action. |

Totals: 21 implemented, 4 experimental, 21 compatible (46 entries). The legend in the directory
header is computed from the data file, so it cannot drift from the entries.

## Considered and omitted

A repository search found no code, docs or adapters for these, and none of them has a clear generic
route, so they are left off rather than implied:

- Observability: OpenTelemetry, Arize Phoenix, LangSmith, Weights & Biases Weave, Braintrust, MLflow, Opik
- Eval frameworks: promptfoo, Inspect, lm-evaluation-harness
- Vector stores: Qdrant, Chroma, pgvector
- Clouds and runtimes: AWS Bedrock, Azure OpenAI, Vertex AI, Cohere, Kubernetes
- Agent frameworks: AutoGen, Haystack

Azure, Vertex and Cohere appear in the code only incidentally (for example a cloud-metadata comment in
`security.py`), which is not support.

## Logos

Logos are served locally from `web/landing/public/assets/landing/logos/`, from lobehub
`icons-static-svg@1.45.0` and `simple-icons@13.21.0`. They were normalised (`currentColor` changed to
white, fixed sizes removed) and checked for scripts and `foreignObject`. LocalAI, LiteLLM, Helicone,
DeepEval and Ragas had no reliable mark, so they use two-letter monograms.

## Visual changes

- The directory changed from four bordered group cards to one panel with six bands. Each band has a
  compact label and role column and wrapping chips.
- Chips are 26px tall with 14px logos, 11.5px labels and 5px gaps (v1 tiles were about 44px).
- On desktop (≥1200px) the engine sits beside the directory. There is one animated path per band
  into its own engine port. The output drops below the directory, curves into EXECUTE, then
  continues into the report. Below 1200px the engine stacks under the directory with a single trunk.
- The engine card lists what it binds: the plan's SHA-256 fingerprint, fail-closed spend ceilings and
  the SQLite WAL results ledger.
- The run timeline and A/B evaluation are merged into one report. On desktop it has two columns:
  26px case rows and 34px metric rows. Below 1024px it becomes one column.
- Unchanged semantics: ESTIMATED and UNAVAILABLE basis tags, null rendered as "—" (never 0),
  agreement labelled "not accuracy", and a sample-run label and footnote.

## Validation

- `npx tsc`, `npm run build`, `npm run build:landing`, `npm run build:site`: pass.
- At 1440, 1366, 1280, 1024, 768, 390 and 375: no horizontal overflow, no broken images, no console
  errors.
- Reduced motion: the complete final state renders at once (6 rows, 9 stages, no particles, ring
  stopped).
- Animation: one rAF clock, worst frame 17ms over 240 frames at 1440.
