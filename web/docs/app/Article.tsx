import React, { useEffect, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, Copy } from 'lucide-react'
import type { Block, CalloutKind, Heading } from './markdown'
import { neighbours, type DocPage } from './content'
import { pageHref } from './router'
import { EDIT_BASE } from './site'

const LANG_LABEL: Record<string, string> = { bash: 'Terminal', sh: 'Terminal', python: 'Python', yaml: 'YAML', json: 'JSON', jsonl: 'JSONL', text: 'Text', toml: 'TOML' }

export const CodeBlock: React.FC<{ code: string; lang?: string }> = ({ code, lang = '' }) => {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code)
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable (insecure context): the text stays selectable */
    }
  }
  const commentable = ['bash', 'sh', 'python', 'yaml', 'toml'].includes(lang)
  return (
    <div className="rd-code">
      <div className="rd-code-bar">
        <span>{LANG_LABEL[lang] ?? (lang || 'Code')}</span>
        <button type="button" onClick={copy} aria-label={copied ? 'Copied' : 'Copy code'}>
          {copied ? <Check size={13} /> : <Copy size={13} />}
          <span>{copied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <pre>
        <code>
          {code.split('\n').map((line, i) => (
            <span key={i} className={commentable && /^\s*#/.test(line) ? 'rd-code-comment' : undefined}>
              {line}
              {'\n'}
            </span>
          ))}
        </code>
      </pre>
    </div>
  )
}

const CALLOUT_LABEL: Record<CalloutKind, string> = { note: 'Note', tip: 'Tip', important: 'Important', warning: 'Warning' }

export const Callout: React.FC<{ kind: CalloutKind; children: React.ReactNode }> = ({ kind, children }) => (
  <aside className={`rd-callout rd-callout-${kind}`} role="note">
    <p className="rd-callout-label">{CALLOUT_LABEL[kind]}</p>
    {children}
  </aside>
)

const Html: React.FC<{ as: 'p' | 'li' | 'th' | 'td' | 'h2' | 'h3'; html: string } & Record<string, unknown>> = ({ as: Tag, html, ...rest }) => (
  <Tag {...rest} dangerouslySetInnerHTML={{ __html: html }} />
)

export const MarkdownBlocks: React.FC<{ blocks: Block[]; slug: string }> = ({ blocks, slug }) => (
  <>
    {blocks.map((b, i) => {
      switch (b.type) {
        case 'heading':
          return (
            <Html key={i} as={b.level === 2 ? 'h2' : 'h3'} id={b.id} className={`rd-h${b.level}`} html={`<a class="rd-anchor" href="${pageHref(slug, b.id)}" aria-hidden="true" tabindex="-1">#</a>${b.html}`} />
          )
        case 'paragraph':
          return <Html key={i} as="p" html={b.html} />
        case 'list': {
          const L = b.ordered ? 'ol' : 'ul'
          return (
            <L key={i}>
              {b.items.map((it, j) => (
                <Html key={j} as="li" html={it} />
              ))}
            </L>
          )
        }
        case 'code':
          return <CodeBlock key={i} code={b.code} lang={b.lang} />
        case 'table':
          return (
            <div key={i} className="rd-table-wrap" tabIndex={0}>
              <table>
                <thead>
                  <tr>
                    {b.head.map((h, j) => (
                      <Html key={j} as="th" html={h} style={{ textAlign: b.align[j] }} />
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {b.rows.map((r, j) => (
                    <tr key={j}>
                      {r.map((c, k) => (
                        <Html key={k} as="td" html={c} style={{ textAlign: b.align[k] }} />
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        case 'callout':
          return (
            <Callout key={i} kind={b.kind}>
              <MarkdownBlocks blocks={b.blocks} slug={slug} />
            </Callout>
          )
        case 'rule':
          return <hr key={i} />
        default:
          return null
      }
    })}
  </>
)

export const TableOfContents: React.FC<{ slug: string; headings: Heading[] }> = ({ slug, headings }) => {
  const [active, setActive] = useState<string | undefined>(headings[0]?.id)

  useEffect(() => {
    if (!headings.length) return
    const els = headings.map((h) => document.getElementById(h.id)).filter(Boolean) as HTMLElement[]
    const onScroll = () => {
      // the last heading whose top has passed 30% of the viewport is the one being read
      const line = window.innerHeight * 0.3
      let cur = els[0]?.id
      for (const el of els) if (el.getBoundingClientRect().top <= line) cur = el.id
      if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 4) cur = els[els.length - 1]?.id
      setActive(cur)
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [slug, headings])

  if (headings.length < 2) return null
  return (
    <nav className="rd-toc" aria-label="On this page">
      <p className="rd-toc-title">On this page</p>
      <ul>
        {headings.map((h) => (
          <li key={h.id} className={h.level === 3 ? 'is-sub' : undefined}>
            <a href={pageHref(slug, h.id)} className={active === h.id ? 'is-active' : undefined} aria-current={active === h.id ? 'location' : undefined}>
              {h.text}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}

export const Pagination: React.FC<{ slug: string }> = ({ slug }) => {
  const { prev, next } = neighbours(slug)
  return (
    <nav className="rd-pager" aria-label="Previous and next pages">
      {prev ? (
        <a href={pageHref(prev.slug)} className="rd-pager-link">
          <span className="rd-pager-dir"><ArrowLeft size={13} aria-hidden="true" /> Previous</span>
          <span className="rd-pager-title">{prev.title}</span>
        </a>
      ) : (
        <span />
      )}
      {next ? (
        <a href={pageHref(next.slug)} className="rd-pager-link rd-pager-next">
          <span className="rd-pager-dir">Next <ArrowRight size={13} aria-hidden="true" /></span>
          <span className="rd-pager-title">{next.title}</span>
        </a>
      ) : (
        <span />
      )}
    </nav>
  )
}

export const ArticleLayout: React.FC<{ page: DocPage }> = ({ page }) => (
  <div className="rd-article-grid">
    <article className="rd-article">
      <header className="rd-article-head">
        <h1>{page.title}</h1>
        {page.description && <p className="rd-lede">{page.description}</p>}
      </header>
      {page.headings.length >= 3 && (
        <details className="rd-toc-inline">
          <summary>On this page</summary>
          <ul>
            {page.headings.filter((h) => h.level === 2).map((h) => (
              <li key={h.id}>
                <a href={pageHref(page.slug, h.id)}>{h.text}</a>
              </li>
            ))}
          </ul>
        </details>
      )}
      <div className="rd-prose">
        <MarkdownBlocks blocks={page.blocks} slug={page.slug} />
      </div>
      <p className="rd-edit">
        <a href={`${EDIT_BASE}/${page.slug}.md`} target="_blank" rel="noopener noreferrer">
          Edit this page on GitHub
        </a>
      </p>
      <Pagination slug={page.slug} />
    </article>
    <TableOfContents slug={page.slug} headings={page.headings} />
  </div>
)
