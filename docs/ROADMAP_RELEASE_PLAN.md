# Roadmap Release Plan

From v0.1.0 (alpha) to v1.0.0. Each version ships only when its acceptance criteria pass in CI. Status and evidence for every
capability are in `docs/ROADMAP_IMPLEMENTATION_AUDIT.md`.

---

## 0. Before anything else: release v0.1.0 for real

`git tag` and `git ls-remote --tags origin` show no tags, so the release workflow (`.github/workflows/release.yml`) has never
published v0.1.0. Decide whether v0.1.0 is the `main` state of 2026-11-03 (tag that commit) or skip straight to v0.2.0.

---

## 1. Versions

| Version | Theme | Contents | Depends on |
|:---|:---|:---|:---|
| **v0.2.0** | Safe foundations and developer integration | F0 integrity fixes; MCP server and client hardening; in-process Python SDK with public result models; capability matrix | merged branch work |
| **v0.3.0** | Agent observability | F1 canonical trace schema and storage; spans from Dify, MCP, RAG; LangGraph streaming adapter with per-node spans; trajectory scorers | v0.2 |
| **v0.4.0** | Remote integration | F3 API keys; F2 async jobs and REST v1; remote Python client; TypeScript SDK; MCP over Streamable HTTP | v0.3 |
| **v0.5.0** | Interoperability | OTel/OpenInference ingestion; Langfuse import (canonical) and export; instrumentation API (decorators, OTel-native) | v0.3, v0.4 |
| **v0.6.0** | Shared deployment | Organizations, projects, RBAC, Postgres, workers, per-project secrets, audit log | v0.4 |
| **v1.0.0** | Stability | Framework adapters (LangChain, CrewAI, PydanticAI, LlamaIndex) on the instrumentation API, security audit, API freeze, migration guide | all |

This differs from the proposal that put SDKs and MCP in v0.2 and multi-user in v0.5: MCP and an in-process SDK already exist and
mainly need hardening, while the remote SDKs depend on identity and async jobs, which should come before them.

---

## 2. v0.2.0 tasks

| Task | Files | Tests |
|:---|:---|:---|
| Cumulative per-run ceiling and atomic budget reservation **(done)** | `core/budget.py`, `runs/executor.py`, `storage/db.py` | Concurrent runs vs a cap; actual cost above estimate stops at the per-run ceiling |
| `RequestEvent` emission from `GenericRunner` **(done)** | `runs/executor.py`, `observability/events.py` | Every executed case yields start and finish events; dashboard stream shows them |
| Persist score kind (`ground_truth` / `judge` / `heuristic`) **(done)** | `runs/executor.py`, `storage/db.py`, UI and reports | Heuristic overlap is never labelled accuracy |
| Fix Compare chart defaults (`|| 50`, `|| 90`) **(done)** | `web/src/App.tsx` | Missing latency renders "unavailable" |
| Public SDK result models | `sdk.py` | SDK returns only public types |
| MCP: protocol `2025-11-25`, version matrix test | `connectors/mcp.py`, `mcp_server/server.py` | Official SDK client against each supported version |
| Dashboard token support (so token mode works with the UI) | `web/src/App.tsx`, `api/app.py` | Browser test with a token |
| Extend mypy to `api/`, `cli/`, `observability/`, fix the ~20 known errors | `pyproject.toml` | CI |
| Green CI on every job (prerequisite for tagging) **(fixes on `claude/ci-green`, pending CI)** | `.github/workflows/ci.yml`, `tests/test_launcher_pty.py` | All CI jobs pass on `main` |
| Tag and publish | `CHANGELOG.md`, release workflow | Wheel installs and `runport web` serves the bundled UI |

**Acceptance:** all v0.2 tests pass; an agent over stdio MCP plans, a person approves, the agent executes and reads results; the
SDK benchmarks a plain function and a workspace HTTP target; no interface can spend without approval (tests per interface).

---

## 3. Later versions: acceptance criteria

- **v0.3.0:** a LangGraph agent's run is reconstructed node by node with tool calls; two versions of an agent are compared on
  tool selection and argument validity; trace round-trip and null-semantics tests pass.
- **v0.4.0:** the same scenario passes through the in-process SDK, the Python client, the TypeScript client and MCP over HTTP
  with scoped keys; OpenAPI diff check in CI.
- **v0.5.0:** recorded OTel GenAI and OpenInference fixtures import into canonical traces and score with the same scorers as
  native runs; a Runport trace exports to Langfuse's ingestion format and re-imports equal.
- **v0.6.0:** section 5 of `docs/MULTI_USER_SECURITY_MODEL.md` passes.
- **v1.0.0:** documented, tested adapters; external security review; no open P0/P1 issues; API and schema frozen.

---

## 4. Verified state

`main` at `b735afc` (2026-11-06), from the GitHub Actions run of the PR #15 merge: lint, mypy, and the Linux, Windows and
macOS 3.11/3.12 test jobs pass; macOS 3.13, the wheel smoke test and the legacy scan fail. Branch `claude/ci-green` fixes
those three and passes locally: 465 tests, plugins 26 passed and 5 skipped, ruff, format, mypy (56 files), web tests (18),
Gitleaks and the legacy scan. Its CI run is the confirmation still outstanding. Details: `docs/ROADMAP_IMPLEMENTATION_AUDIT.md`, section 1.
