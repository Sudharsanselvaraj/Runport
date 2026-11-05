// Documentation registry: the sidebar order lives here; page text lives in
// docs/content/<slug>.md with `title` and `description` front matter.
import { blockText, parseMarkdown, type ParsedDoc } from './markdown'

export interface NavGroup {
  title: string
  pages: string[]
}

export const NAV: NavGroup[] = [
  { title: 'Getting started', pages: ['introduction', 'installation', 'quickstart', 'integrating-projects'] },
  { title: 'Core concepts', pages: ['architecture', 'benchmarks', 'runs-and-plans', 'datasets', 'invariants'] },
  { title: 'Model providers', pages: ['openai-compatible', 'openrouter', 'ollama', 'vllm', 'custom-http'] },
  { title: 'Benchmarking', pages: ['creating-benchmarks', 'executing-runs', 'rag-benchmarks', 'reproducibility'] },
  { title: 'Evaluation', pages: ['scorers', 'classification', 'generation', 'extraction', 'rag-evaluation', 'ground-truth'] },
  { title: 'Metrics and analysis', pages: ['latency', 'token-usage', 'cost-analysis', 'quality-metrics'] },
  { title: 'Integrations', pages: ['dify', 'langgraph', 'n8n', 'flowise', 'langflow', 'mcp', 'python-integrations', 'plugins'] },
  { title: 'CLI reference', pages: ['cli-overview', 'cli-commands', 'cli-budget', 'cli-examples'] },
  { title: 'Configuration', pages: ['workspace-file', 'environment-variables', 'budget-guardrails', 'approval-policies', 'provider-configuration'] },
  { title: 'Results and reports', pages: ['understanding-results', 'comparing-runs', 'exporting-traces', 'dashboards'] },
  { title: 'Troubleshooting', pages: ['common-errors', 'provider-errors', 'faq'] },
  { title: 'Contributing', pages: ['development-setup', 'running-tests', 'contribution-guidelines'] },
]

export interface DocPage extends ParsedDoc {
  slug: string
  title: string
  description: string
  group: string
}

const raw = import.meta.glob('../content/*.md', { query: '?raw', import: 'default', eager: true }) as Record<string, string>

const bySlug = new Map<string, DocPage>()
for (const [path, src] of Object.entries(raw)) {
  const slug = path.replace(/^.*\/(.+)\.md$/, '$1')
  const parsed = parseMarkdown(src)
  const group = NAV.find((g) => g.pages.includes(slug))?.title ?? ''
  bySlug.set(slug, {
    ...parsed,
    slug,
    title: parsed.meta.title ?? slug,
    description: parsed.meta.description ?? '',
    group,
  })
}

/** Pages in sidebar order. A nav entry without a content file is a build-time bug; it is reported, not hidden. */
export const ORDER: DocPage[] = NAV.flatMap((g) =>
  g.pages.map((slug) => {
    const page = bySlug.get(slug)
    if (!page) throw new Error(`docs: nav entry "${slug}" has no content/${slug}.md`)
    return page
  }),
)

export const getPage = (slug: string) => bySlug.get(slug)

export function neighbours(slug: string): { prev?: DocPage; next?: DocPage } {
  const i = ORDER.findIndex((p) => p.slug === slug)
  return { prev: ORDER[i - 1], next: ORDER[i + 1] }
}

// ---------- search index ----------

export interface SearchEntry {
  slug: string
  pageTitle: string
  group: string
  heading?: string
  headingId?: string
  text: string
}

/** One entry per page intro plus one per ## / ### section. */
export const SEARCH_INDEX: SearchEntry[] = ORDER.flatMap((page) => {
  const entries: SearchEntry[] = []
  let current: SearchEntry = { slug: page.slug, pageTitle: page.title, group: page.group, text: page.description }
  entries.push(current)
  for (const b of page.blocks) {
    if (b.type === 'heading') {
      current = { slug: page.slug, pageTitle: page.title, group: page.group, heading: b.text, headingId: b.id, text: '' }
      entries.push(current)
    } else {
      current.text += ' ' + blockText(b)
    }
  }
  return entries
})

export interface SearchHit extends SearchEntry {
  score: number
  snippet: string
}

const norm = (s: string) => s.toLowerCase()

export function search(query: string, limit = 12): SearchHit[] {
  const terms = norm(query).split(/\s+/).filter(Boolean)
  if (!terms.length) return []
  const hits: SearchHit[] = []
  for (const e of SEARCH_INDEX) {
    const title = norm(e.pageTitle)
    const heading = norm(e.heading ?? '')
    const text = norm(e.text)
    let score = 0
    let all = true
    for (const t of terms) {
      const inTitle = title.includes(t)
      const inHeading = heading.includes(t)
      const inText = text.includes(t)
      if (!inTitle && !inHeading && !inText) {
        all = false
        break
      }
      score += (inTitle ? 10 : 0) + (inHeading ? 6 : 0) + (inText ? 1 : 0)
      if (title.startsWith(t)) score += 4
    }
    if (!all) continue
    if (!e.heading) score += 2 // prefer the page itself over its sections on ties
    hits.push({ ...e, score, snippet: makeSnippet(e.text, terms) })
  }
  hits.sort((a, b) => b.score - a.score)
  // keep at most three sections per page so one long article does not crowd out the rest
  const perPage = new Map<string, number>()
  return hits.filter((h) => {
    const n = perPage.get(h.slug) ?? 0
    perPage.set(h.slug, n + 1)
    return n < 3
  }).slice(0, limit)
}

function makeSnippet(text: string, terms: string[]): string {
  const clean = text.replace(/\s+/g, ' ').trim()
  const lower = clean.toLowerCase()
  let at = -1
  for (const t of terms) {
    const i = lower.indexOf(t)
    if (i !== -1 && (at === -1 || i < at)) at = i
  }
  if (at === -1) return clean.slice(0, 140)
  const start = Math.max(0, at - 50)
  return (start > 0 ? '…' : '') + clean.slice(start, start + 150) + (start + 150 < clean.length ? '…' : '')
}
