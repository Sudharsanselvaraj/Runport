// A small Markdown reader for the docs content. It covers only what the pages
// use: front matter, ## / ### headings, paragraphs, lists, fenced code, tables,
// callouts (> [!NOTE]) and inline code, bold, italics and links. No dependency.

export type CalloutKind = 'note' | 'tip' | 'important' | 'warning'

export type Block =
  | { type: 'heading'; level: 2 | 3; id: string; text: string; html: string }
  | { type: 'paragraph'; html: string }
  | { type: 'list'; ordered: boolean; items: string[] }
  | { type: 'code'; lang: string; code: string }
  | { type: 'table'; head: string[]; rows: string[][]; align: ('left' | 'right' | 'center')[] }
  | { type: 'callout'; kind: CalloutKind; blocks: Block[] }
  | { type: 'rule' }

export interface Heading {
  level: 2 | 3
  id: string
  text: string
}

export interface ParsedDoc {
  meta: Record<string, string>
  blocks: Block[]
  headings: Heading[]
}

const escapeHtml = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')

export const slugify = (s: string) =>
  s
    .toLowerCase()
    .replace(/`/g, '')
    .replace(/[^a-z0-9\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')

/** Turns a Markdown href into a portal href. `/slug` and `/slug#id` become hash routes. */
export function resolveHref(href: string): { href: string; external: boolean } {
  if (/^https?:\/\//.test(href) || href.startsWith('mailto:')) return { href, external: true }
  if (href.startsWith('/')) return { href: `#${href}`, external: false }
  return { href, external: false }
}

/** Inline Markdown to HTML. Code spans are protected first so their contents stay literal. */
export function inline(src: string): string {
  const parts = src.split(/(`[^`]+`)/g)
  return parts
    .map((part) => {
      if (part.startsWith('`') && part.endsWith('`') && part.length > 1) {
        return `<code>${escapeHtml(part.slice(1, -1))}</code>`
      }
      let s = escapeHtml(part)
      s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_m, text: string, url: string) => {
        const { href, external } = resolveHref(url.replace(/&amp;/g, '&'))
        const ext = external ? ' target="_blank" rel="noopener noreferrer"' : ''
        return `<a href="${escapeHtml(href)}"${ext}>${text}</a>`
      })
      s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
      s = s.replace(/(^|[\s(])\*([^*\s][^*]*)\*(?=[\s).,;:!?]|$)/g, '$1<em>$2</em>')
      return s
    })
    .join('')
}

/** Plain text of an inline Markdown string, for search and heading ids. */
export const plain = (src: string) =>
  src
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/\*([^*]+)\*/g, '$1')

function parseFrontMatter(src: string): { meta: Record<string, string>; body: string } {
  const meta: Record<string, string> = {}
  if (!src.startsWith('---\n')) return { meta, body: src }
  const end = src.indexOf('\n---', 4)
  if (end === -1) return { meta, body: src }
  for (const line of src.slice(4, end).split('\n')) {
    const i = line.indexOf(':')
    if (i > 0) meta[line.slice(0, i).trim()] = line.slice(i + 1).trim().replace(/^["']|["']$/g, '')
  }
  return { meta, body: src.slice(end + 4).replace(/^\n+/, '') }
}

const splitRow = (line: string) =>
  line
    .trim()
    .replace(/^\|/, '')
    .replace(/\|$/, '')
    .split(/(?<!\\)\|/)
    .map((c) => c.trim().replace(/\\\|/g, '|'))

function parseBlocks(lines: string[], ids: Map<string, number>, headings: Heading[]): Block[] {
  const blocks: Block[] = []
  let i = 0
  const isBlank = (l: string) => l.trim() === ''
  const startsBlock = (l: string) =>
    /^#{2,3}\s/.test(l) || /^```/.test(l) || /^>\s?/.test(l) || /^\s*([-*]|\d+\.)\s/.test(l) || /^\|/.test(l) || /^---\s*$/.test(l)

  while (i < lines.length) {
    const line = lines[i]
    if (isBlank(line)) {
      i++
      continue
    }

    const h = /^(#{2,3})\s+(.*)$/.exec(line)
    if (h) {
      const level = h[1].length as 2 | 3
      const text = plain(h[2]).trim()
      let id = slugify(text) || 'section'
      const n = ids.get(id) ?? 0
      ids.set(id, n + 1)
      if (n > 0) id = `${id}-${n}`
      headings.push({ level, id, text })
      blocks.push({ type: 'heading', level, id, text, html: inline(h[2]) })
      i++
      continue
    }

    if (/^```/.test(line)) {
      const lang = line.slice(3).trim()
      const code: string[] = []
      i++
      while (i < lines.length && !/^```\s*$/.test(lines[i])) code.push(lines[i++])
      i++
      blocks.push({ type: 'code', lang, code: code.join('\n') })
      continue
    }

    if (/^---\s*$/.test(line)) {
      blocks.push({ type: 'rule' })
      i++
      continue
    }

    if (/^>\s?/.test(line)) {
      const inner: string[] = []
      while (i < lines.length && /^>\s?/.test(lines[i])) inner.push(lines[i++].replace(/^>\s?/, ''))
      const m = /^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$/i.exec(inner[0] ?? '')
      const raw = m ? m[1].toLowerCase() : 'note'
      const kind = (raw === 'caution' ? 'warning' : raw) as CalloutKind
      blocks.push({ type: 'callout', kind, blocks: parseBlocks(m ? inner.slice(1) : inner, ids, headings) })
      continue
    }

    if (/^\|/.test(line) && i + 1 < lines.length && /^\|?\s*:?-{2,}/.test(lines[i + 1])) {
      const head = splitRow(line).map(inline)
      const align = splitRow(lines[i + 1]).map((c) =>
        c.startsWith(':') && c.endsWith(':') ? 'center' : c.endsWith(':') ? 'right' : 'left',
      ) as ('left' | 'right' | 'center')[]
      i += 2
      const rows: string[][] = []
      while (i < lines.length && /^\|/.test(lines[i])) rows.push(splitRow(lines[i++]).map(inline))
      blocks.push({ type: 'table', head, rows, align })
      continue
    }

    const li = /^\s*([-*]|\d+\.)\s+(.*)$/.exec(line)
    if (li) {
      const ordered = /\d/.test(li[1])
      const items: string[] = []
      while (i < lines.length) {
        const m = /^\s*([-*]|\d+\.)\s+(.*)$/.exec(lines[i])
        if (m) {
          items.push(m[2])
          i++
        } else if (!isBlank(lines[i]) && /^\s{2,}\S/.test(lines[i]) && items.length) {
          items[items.length - 1] += ' ' + lines[i].trim()
          i++
        } else break
      }
      blocks.push({ type: 'list', ordered, items: items.map(inline) })
      continue
    }

    const para: string[] = []
    while (i < lines.length && !isBlank(lines[i]) && !(para.length && startsBlock(lines[i]))) para.push(lines[i++].trim())
    blocks.push({ type: 'paragraph', html: inline(para.join(' ')) })
  }
  return blocks
}

export function parseMarkdown(src: string): ParsedDoc {
  const { meta, body } = parseFrontMatter(src.replace(/\r\n/g, '\n'))
  const headings: Heading[] = []
  const blocks = parseBlocks(body.split('\n'), new Map(), headings)
  return { meta, blocks, headings }
}

/** Plain text of a block list, used to build the search index. */
export function blockText(b: Block): string {
  const strip = (html: string) => html.replace(/<[^>]+>/g, '').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&amp;/g, '&')
  switch (b.type) {
    case 'heading':
      return b.text
    case 'paragraph':
      return strip(b.html)
    case 'list':
      return b.items.map(strip).join(' ')
    case 'code':
      return b.code
    case 'table':
      return [...b.head, ...b.rows.flat()].map(strip).join(' ')
    case 'callout':
      return b.blocks.map(blockText).join(' ')
    default:
      return ''
  }
}
