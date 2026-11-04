import React from 'react'
import { Menu, Search } from 'lucide-react'
import { REPO_URL, SITE_URL } from './site'
import { pageHref } from './router'

export interface Crumb {
  label: string
  href?: string
}

export const Breadcrumbs: React.FC<{ items: Crumb[] }> = ({ items }) => (
  <nav className="rd-crumbs" aria-label="Breadcrumb">
    <ol>
      {items.map((c, i) => {
        const last = i === items.length - 1
        return (
          <li key={`${c.label}-${i}`}>
            {c.href && !last ? <a href={c.href}>{c.label}</a> : <span aria-current={last ? 'page' : undefined}>{c.label}</span>}
          </li>
        )
      })}
    </ol>
  </nav>
)

interface DocsHeaderProps {
  crumbs: Crumb[]
  onMenu: () => void
  onSearch: () => void
}

export const DocsHeader: React.FC<DocsHeaderProps> = ({ crumbs, onMenu, onSearch }) => (
  <header className="rd-header">
    <button type="button" className="rd-icon-btn rd-menu-btn" onClick={onMenu} aria-label="Open navigation">
      <Menu size={16} />
    </button>
    <a href={pageHref('')} className="rd-brand rd-header-brand">
      <span className="rd-wordmark">RUNPORT</span>
      <span className="rd-brand-sep" aria-hidden="true" />
      <span className="rd-brand-label">Docs</span>
    </a>
    <Breadcrumbs items={crumbs} />
    <div className="rd-header-actions">
      <button type="button" className="rd-search-trigger" onClick={onSearch} aria-label="Search documentation">
        <Search size={14} aria-hidden="true" />
        <span className="rd-search-label">Search</span>
        <kbd>⌘K</kbd>
      </button>
      <a className="rd-pill rd-pill-quiet rd-hide-sm" href={SITE_URL}>
        Website
      </a>
      <a className="rd-pill" href={REPO_URL} target="_blank" rel="noopener noreferrer">
        GitHub
      </a>
    </div>
  </header>
)

interface DocumentationLayoutProps {
  sidebar: React.ReactNode
  header: React.ReactNode
  /** dialogs that must inherit the portal's tokens (rendered inside .rd) */
  overlay?: React.ReactNode
  children: React.ReactNode
}

export const DocumentationLayout: React.FC<DocumentationLayoutProps> = ({ sidebar, header, overlay, children }) => (
  <div className="rd">
    <a className="rd-skip" href="#rd-main" onClick={(e) => { e.preventDefault(); document.getElementById('rd-main')?.focus() }}>
      Skip to content
    </a>
    {sidebar}
    <div className="rd-main-col">
      {header}
      <main id="rd-main" tabIndex={-1} className="rd-main">
        {children}
      </main>
    </div>
    {overlay}
  </div>
)
