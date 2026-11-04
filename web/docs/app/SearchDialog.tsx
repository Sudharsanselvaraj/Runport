import React, { useEffect, useMemo, useRef, useState } from 'react'
import { CornerDownLeft, Search } from 'lucide-react'
import { search, type SearchHit } from './content'
import { navigate } from './router'

const SUGGESTED = ['quickstart', 'budget', 'replay', 'Dify', 'Wilson', 'reconcile']

function highlight(text: string, query: string): React.ReactNode {
  const terms = query.toLowerCase().split(/\s+/).filter(Boolean).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  if (!terms.length) return text
  const re = new RegExp(`(${terms.join('|')})`, 'gi')
  return text.split(re).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part))
}

interface SearchDialogProps {
  open: boolean
  onClose: () => void
}

export const SearchDialog: React.FC<SearchDialogProps> = ({ open, onClose }) => {
  const [query, setQuery] = useState('')
  const [sel, setSel] = useState(0)
  const input = useRef<HTMLInputElement>(null)
  const list = useRef<HTMLUListElement>(null)
  const hits = useMemo(() => search(query), [query])

  useEffect(() => {
    if (open) {
      setQuery('')
      setSel(0)
      window.setTimeout(() => input.current?.focus(), 0)
    }
  }, [open])
  useEffect(() => setSel(0), [query])
  useEffect(() => {
    list.current?.querySelector<HTMLElement>(`[data-i="${sel}"]`)?.scrollIntoView({ block: 'nearest' })
  }, [sel])

  if (!open) return null

  const go = (h: SearchHit) => {
    onClose()
    navigate(h.slug, h.headingId)
  }

  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setSel((s) => Math.min(s + 1, hits.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setSel((s) => Math.max(s - 1, 0))
    } else if (e.key === 'Enter' && hits[sel]) {
      e.preventDefault()
      go(hits[sel])
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    }
  }

  return (
    <div className="rd-search-scrim" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="rd-search" role="dialog" aria-modal="true" aria-label="Search documentation" onKeyDown={onKey}>
        <div className="rd-search-field">
          <Search size={16} aria-hidden="true" />
          <input
            ref={input}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search the documentation"
            aria-label="Search the documentation"
            role="combobox"
            aria-expanded={hits.length > 0}
            aria-controls="rd-search-results"
            aria-activedescendant={hits[sel] ? `rd-hit-${sel}` : undefined}
            autoComplete="off"
            spellCheck={false}
          />
          <kbd>Esc</kbd>
        </div>

        {query.trim() === '' ? (
          <div className="rd-search-empty">
            <p>Search page titles, sections and article text.</p>
            <div className="rd-search-suggest">
              {SUGGESTED.map((s) => (
                <button key={s} type="button" onClick={() => setQuery(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : hits.length === 0 ? (
          <div className="rd-search-empty">
            <p>
              No results for <strong>“{query}”</strong>.
            </p>
            <p className="rd-search-hint">Try a command name such as <code>benchmark</code>, a connector such as <code>ollama</code>, or a term such as <code>provenance</code>.</p>
          </div>
        ) : (
          <ul id="rd-search-results" ref={list} className="rd-search-results" role="listbox">
            {hits.map((h, i) => (
              <li
                key={`${h.slug}-${h.headingId ?? ''}`}
                id={`rd-hit-${i}`}
                data-i={i}
                role="option"
                aria-selected={i === sel}
                className={i === sel ? 'is-selected' : undefined}
                onMouseMove={() => setSel(i)}
                onClick={() => go(h)}
              >
                <span className="rd-hit-path">
                  {h.group} <span aria-hidden="true">/</span> {highlight(h.pageTitle, query)}
                  {h.heading && (
                    <>
                      {' '}<span aria-hidden="true">/</span> {highlight(h.heading, query)}
                    </>
                  )}
                </span>
                <span className="rd-hit-snippet">{highlight(h.snippet, query)}</span>
                {i === sel && <CornerDownLeft size={13} className="rd-hit-enter" aria-hidden="true" />}
              </li>
            ))}
          </ul>
        )}
        <div className="rd-search-foot">
          <span><kbd>↑</kbd><kbd>↓</kbd> to move</span>
          <span><kbd>↵</kbd> to open</span>
          <span><kbd>Esc</kbd> to close</span>
        </div>
      </div>
    </div>
  )
}
