import React, { useEffect, useState } from 'react'
import { ChevronRight, Search } from 'lucide-react'
import { NAV, getPage, type NavGroup } from './content'
import { pageHref } from './router'
import { ISSUES_URL, REPO_URL, SITE_URL } from './site'

interface SidebarLinkProps {
  slug: string
  active: boolean
  onNavigate?: () => void
}

export const SidebarLink: React.FC<SidebarLinkProps> = ({ slug, active, onNavigate }) => {
  const page = getPage(slug)
  if (!page) return null
  return (
    <a
      href={pageHref(slug)}
      className={`rd-side-link${active ? ' is-active' : ''}`}
      aria-current={active ? 'page' : undefined}
      onClick={onNavigate}
    >
      {page.title}
    </a>
  )
}

interface SidebarGroupProps {
  group: NavGroup
  open: boolean
  current: string
  onToggle: () => void
  onNavigate?: () => void
}

export const SidebarGroup: React.FC<SidebarGroupProps> = ({ group, open, current, onToggle, onNavigate }) => {
  const id = `rd-group-${group.title.toLowerCase().replace(/\s+/g, '-')}`
  const holdsCurrent = group.pages.includes(current)
  return (
    <div className="rd-side-group">
      <button
        type="button"
        className={`rd-side-head${holdsCurrent ? ' holds-current' : ''}`}
        aria-expanded={open}
        aria-controls={id}
        onClick={onToggle}
      >
        <span>{group.title}</span>
        <ChevronRight size={14} className="rd-chevron" aria-hidden="true" />
      </button>
      <div id={id} className="rd-side-pages" hidden={!open}>
        {group.pages.map((slug) => (
          <SidebarLink key={slug} slug={slug} active={slug === current} onNavigate={onNavigate} />
        ))}
      </div>
    </div>
  )
}

interface SidebarProps {
  current: string
  open: boolean
  onClose: () => void
  onSearch: () => void
}

export const Sidebar: React.FC<SidebarProps> = ({ current, open, onClose, onSearch }) => {
  const groupOf = (slug: string) => NAV.find((g) => g.pages.includes(slug))?.title
  const [expanded, setExpanded] = useState<Set<string>>(() => new Set([groupOf(current) ?? NAV[0].title]))

  // the group holding the current page always opens; groups the reader opened stay open
  useEffect(() => {
    const g = groupOf(current)
    if (g) setExpanded((s) => (s.has(g) ? s : new Set(s).add(g)))
  }, [current])

  const toggle = (title: string) =>
    setExpanded((s) => {
      const n = new Set(s)
      n.has(title) ? n.delete(title) : n.add(title)
      return n
    })

  return (
    <>
      <div className={`rd-scrim${open ? ' is-open' : ''}`} onClick={onClose} aria-hidden="true" />
      <aside className={`rd-sidebar${open ? ' is-open' : ''}`} aria-label="Documentation">
        <div className="rd-side-top">
          <a href="#/" className="rd-brand" onClick={onClose}>
            <span className="rd-wordmark">RUNPORT</span>
            <span className="rd-brand-sep" aria-hidden="true" />
            <span className="rd-brand-label">Docs</span>
          </a>
          <button type="button" className="rd-icon-btn" onClick={onSearch} aria-label="Search documentation">
            <Search size={15} />
          </button>
        </div>
        <nav className="rd-side-scroll" aria-label="Documentation sections">
          <a href="#/" className={`rd-side-link rd-side-home${current === '' ? ' is-active' : ''}`} onClick={onClose}>
            Overview
          </a>
          {NAV.map((g) => (
            <SidebarGroup
              key={g.title}
              group={g}
              open={expanded.has(g.title)}
              current={current}
              onToggle={() => toggle(g.title)}
              onNavigate={onClose}
            />
          ))}
        </nav>
        <div className="rd-side-foot">
          <a href={SITE_URL}>Website</a>
          <a href={REPO_URL} target="_blank" rel="noopener noreferrer">GitHub</a>
          <a href={ISSUES_URL} target="_blank" rel="noopener noreferrer">Report an issue</a>
        </div>
      </aside>
    </>
  )
}
