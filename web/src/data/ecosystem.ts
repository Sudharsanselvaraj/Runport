// Runport ecosystem shown on the landing page. One source of truth for the
// integration directory: every entry states how Runport reaches it and the
// repository evidence for that claim. See docs/ecosystem-visualization-audit.md.
//
//   native  — a dedicated connector, adapter or module exists in src/runport
//   exp     — a dedicated connector exists but is marked experimental
//   compat  — no dedicated connector; works through a generic one (`via`)
//
// Planned or unrelated technologies are deliberately not listed.

export type EcoStatus = 'native' | 'exp' | 'compat'

export interface EcoItem {
  name: string
  status: EcoStatus
  /** How Runport reaches it when there is no dedicated connector. */
  via?: string
  logo?: string
  icon?: 'globe' | 'terminal' | 'replay' | 'puzzle' | 'target' | 'regex' | 'braces' | 'text' | 'search' | 'gavel' | 'database' | 'file' | 'download' | 'upload'
  /** Two-letter fallback when no reliable logo is available. */
  mono?: string
  evidence: string
}

export interface EcoGroup {
  key: string
  label: string
  role: string
  items: EcoItem[]
}

const L = '/assets/landing/logos/'
const OR = 'via OpenRouter'
const OA = 'via OpenAI-compatible connector'

export const ECOSYSTEM: EcoGroup[] = [
  {
    key: 'providers',
    label: 'Model providers',
    role: 'Hosted models',
    items: [
      { name: 'OpenAI', status: 'native', logo: `${L}openai.svg`, evidence: 'connectors/openai_compat.py (default base_url api.openai.com)' },
      { name: 'OpenRouter', status: 'native', logo: `${L}openrouter.svg`, evidence: 'providers/openrouter.py' },
      { name: 'Anthropic', status: 'compat', via: OR, logo: `${L}anthropic.svg`, evidence: 'Routed by model ID through providers/openrouter.py' },
      { name: 'Gemini', status: 'compat', via: OR, logo: `${L}gemini.svg`, evidence: 'Default CLI model google/gemini-* via OpenRouter' },
      { name: 'Mistral', status: 'compat', via: OR, logo: `${L}mistral.svg`, evidence: 'Routed by model ID through OpenRouter' },
      { name: 'Llama', status: 'compat', via: OR, logo: `${L}meta.svg`, evidence: 'Routed by model ID through OpenRouter' },
      { name: 'DeepSeek', status: 'compat', via: OR, logo: `${L}deepseek.svg`, evidence: 'Routed by model ID through OpenRouter' },
      { name: 'Groq', status: 'compat', via: OA, logo: `${L}groq.svg`, evidence: 'OpenAI-compatible endpoint; OpenAICompatConnector(base_url=…)' },
      { name: 'Together', status: 'compat', via: OA, logo: `${L}together.svg`, evidence: 'OpenAI-compatible endpoint; OpenAICompatConnector(base_url=…)' },
      { name: 'Fireworks', status: 'compat', via: OA, logo: `${L}fireworks.svg`, evidence: 'OpenAI-compatible endpoint; OpenAICompatConnector(base_url=…)' },
      { name: 'DeepInfra', status: 'compat', via: OA, logo: `${L}deepinfra.svg`, evidence: 'OpenAI-compatible endpoint; OpenAICompatConnector(base_url=…)' },
    ],
  },
  {
    key: 'local',
    label: 'Local inference',
    role: 'Self-hosted serving',
    items: [
      { name: 'Ollama', status: 'native', logo: `${L}ollama.svg`, evidence: 'connectors/ollama.py' },
      { name: 'vLLM', status: 'compat', via: OA, logo: `${L}vllm.svg`, evidence: 'Named in connectors/openai_compat.py docstring' },
      { name: 'LM Studio', status: 'compat', via: OA, logo: `${L}lmstudio.svg`, evidence: 'Local OpenAI-compatible server' },
      { name: 'LocalAI', status: 'compat', via: OA, mono: 'LA', evidence: 'Named in connectors/openai_compat.py docstring' },
      { name: 'HF TGI', status: 'compat', via: OA, logo: `${L}huggingface.svg`, evidence: 'TGI serves an OpenAI-compatible Messages API' },
      { name: 'LiteLLM proxy', status: 'compat', via: OA, mono: 'LL', evidence: 'OpenAI-compatible proxy endpoint' },
    ],
  },
  {
    key: 'workflows',
    label: 'Workflows & agents',
    role: 'Orchestrated targets',
    items: [
      { name: 'Dify', status: 'native', logo: `${L}dify.svg`, evidence: 'connectors/dify.py' },
      { name: 'LangGraph', status: 'exp', logo: `${L}langgraph.svg`, evidence: 'connectors/langgraph.py (experimental)' },
      { name: 'Flowise', status: 'exp', logo: `${L}flowise.png`, evidence: 'connectors/flowise.py (experimental)' },
      { name: 'Langflow', status: 'exp', logo: `${L}langflow.svg`, evidence: 'connectors/langflow.py (experimental)' },
      { name: 'n8n', status: 'exp', logo: `${L}n8n.svg`, evidence: 'connectors/n8n.py (experimental)' },
      { name: 'LangChain', status: 'compat', via: 'via Python callable', logo: `${L}langchain.svg`, evidence: 'Wrap chain.invoke in PythonCallableTarget' },
      { name: 'LlamaIndex', status: 'compat', via: 'via Python callable', logo: `${L}llamaindex.svg`, evidence: 'Wrap query_engine.query in PythonCallableTarget' },
      { name: 'CrewAI', status: 'compat', via: 'via Python callable', logo: `${L}crewai.svg`, evidence: 'Wrap crew.kickoff in PythonCallableTarget' },
    ],
  },
  {
    key: 'evaluation',
    label: 'Evaluation & scoring',
    role: 'How outputs are judged',
    items: [
      { name: 'Exact & regex', status: 'native', icon: 'regex', evidence: 'scorers/match.py' },
      { name: 'Classification', status: 'native', icon: 'target', evidence: 'scorers/classification.py, classification/' },
      { name: 'Extraction', status: 'native', icon: 'braces', evidence: 'scorers/extraction.py' },
      { name: 'Generation', status: 'native', icon: 'text', evidence: 'scorers/generation.py' },
      { name: 'RAG metrics', status: 'native', icon: 'search', evidence: 'rag/evaluator.py' },
      { name: 'LLM judge', status: 'native', icon: 'gavel', evidence: 'scorers/llm_judge.py (your judge function)' },
      { name: 'DeepEval', status: 'compat', via: 'via scorer plugin', mono: 'DE', evidence: 'Wrap a metric as a runport.scorers entry point (core/plugins.py)' },
      { name: 'Ragas', status: 'compat', via: 'via scorer plugin', mono: 'RA', evidence: 'Wrap a metric as a runport.scorers entry point (core/plugins.py)' },
    ],
  },
  {
    key: 'data',
    label: 'Data & traces',
    role: 'Inputs and evidence',
    items: [
      { name: 'JSONL datasets', status: 'native', icon: 'file', evidence: 'schemas/evaluation.py, validate-dataset' },
      { name: 'SQLite WAL', status: 'native', logo: `${L}sqlite.svg`, evidence: 'storage/db.py' },
      { name: 'BM25 retriever', status: 'native', icon: 'search', evidence: 'rag/retriever.py' },
      { name: 'Trace export', status: 'native', icon: 'download', evidence: 'export-traces (JSONL, CSV, ZIP)' },
      { name: 'Langfuse', status: 'native', logo: `${L}langfuse.svg`, evidence: 'import-traces reads Langfuse JSON/CSV exports' },
      { name: 'Helicone', status: 'compat', via: OA, mono: 'HE', evidence: 'Gateway base_url plus custom_headers on OpenAICompatConnector' },
    ],
  },
  {
    key: 'execution',
    label: 'Execution & infra',
    role: 'Where targets run',
    items: [
      { name: 'HTTP endpoint', status: 'native', icon: 'globe', evidence: 'connectors/http_workflow.py' },
      { name: 'Python callable', status: 'native', logo: `${L}python.svg`, evidence: 'connectors/python_target.py' },
      { name: 'Subprocess', status: 'native', icon: 'terminal', evidence: 'connectors/python_target.py (SubprocessTarget)' },
      { name: 'Replay', status: 'native', icon: 'replay', evidence: 'runs/replay.py' },
      { name: 'Plugins', status: 'native', icon: 'puzzle', evidence: 'core/plugins.py entry points' },
      { name: 'Docker', status: 'native', logo: `${L}docker.svg`, evidence: 'Dockerfile' },
      { name: 'GitHub Actions', status: 'compat', via: 'runs replay in CI', logo: `${L}githubactions.svg`, evidence: '.github/workflows/ci.yml; replay needs no key' },
    ],
  },
]

export const ECO_COUNTS = ECOSYSTEM.reduce(
  (n, g) => {
    g.items.forEach((i) => (n[i.status] += 1))
    return n
  },
  { native: 0, exp: 0, compat: 0 } as Record<EcoStatus, number>,
)
