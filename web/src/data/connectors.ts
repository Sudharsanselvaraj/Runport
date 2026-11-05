// Connectors shown on the landing page. Mirrors the status matrix in
// docs/connectors/README.md (one row per connector type there, same status).
// tests/test_landing_content.py fails if this file and that matrix disagree or
// a connector module is missing, so the counts on the page stay true.

export type ConnectorStatus = 'supported' | 'experimental'

export interface Connector {
  /** Connector type exactly as listed in docs/connectors/README.md. */
  id: string
  name: string
  status: ConnectorStatus
  /** Module that implements it, relative to src/runport/. */
  module: string
  logo?: string
  icon?: 'globe' | 'terminal'
}

const L = '/assets/landing/logos/'

export const CONNECTORS: Connector[] = [
  { id: 'openai_compat', name: 'OpenAI-compatible', status: 'supported', module: 'connectors/openai_compat.py', logo: `${L}openai.svg` },
  { id: 'openrouter', name: 'OpenRouter', status: 'supported', module: 'providers/openrouter.py', logo: `${L}openrouter.svg` },
  { id: 'dify', name: 'Dify', status: 'supported', module: 'connectors/dify.py', logo: `${L}dify.svg` },
  { id: 'http_workflow', name: 'HTTP endpoint', status: 'supported', module: 'connectors/http_workflow.py', icon: 'globe' },
  { id: 'python_target', name: 'Python callable', status: 'supported', module: 'connectors/python_target.py', logo: `${L}python.svg` },
  { id: 'subprocess', name: 'Subprocess', status: 'supported', module: 'connectors/python_target.py', icon: 'terminal' },
  { id: 'ollama', name: 'Ollama', status: 'supported', module: 'connectors/ollama.py', logo: `${L}ollama.svg` },
  { id: 'flowise', name: 'Flowise', status: 'experimental', module: 'connectors/flowise.py', logo: `${L}flowise.png` },
  { id: 'langflow', name: 'Langflow', status: 'experimental', module: 'connectors/langflow.py', logo: `${L}langflow.svg` },
  { id: 'n8n', name: 'n8n', status: 'experimental', module: 'connectors/n8n.py', logo: `${L}n8n.svg` },
  { id: 'langgraph', name: 'LangGraph', status: 'experimental', module: 'connectors/langgraph.py', logo: `${L}langgraph.svg` },
  { id: 'mcp', name: 'MCP server', status: 'experimental', module: 'connectors/mcp.py', icon: 'terminal' },
]

export const CONNECTOR_COUNTS = {
  total: CONNECTORS.length,
  supported: CONNECTORS.filter((c) => c.status === 'supported').length,
  experimental: CONNECTORS.filter((c) => c.status === 'experimental').length,
}

/**
 * Hosted providers and servers with no adapter of their own. They are reached
 * through a supported connector (`via`), so they inherit its status and are
 * always grouped under "via OpenRouter / OpenAI-compatible", never shown as native.
 */
export interface ViaProvider {
  name: string
  via: 'openrouter' | 'openai_compat'
  logo: string
}

export const VIA_PROVIDERS: ViaProvider[] = [
  { name: 'Anthropic', via: 'openrouter', logo: `${L}anthropic.svg` },
  { name: 'Gemini', via: 'openrouter', logo: `${L}gemini.svg` },
  { name: 'Mistral', via: 'openrouter', logo: `${L}mistral.svg` },
  { name: 'DeepSeek', via: 'openrouter', logo: `${L}deepseek.svg` },
  { name: 'Groq', via: 'openai_compat', logo: `${L}groq.svg` },
  { name: 'Together', via: 'openai_compat', logo: `${L}together.svg` },
  { name: 'vLLM', via: 'openai_compat', logo: `${L}vllm.svg` },
]

export const connectorById = (id: string): Connector => {
  const c = CONNECTORS.find((x) => x.id === id)
  if (!c) throw new Error(`unknown connector ${id}`)
  return c
}

export const STATUS_LABEL: Record<ConnectorStatus, string> = { supported: 'Supported', experimental: 'Experimental' }
