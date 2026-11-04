import React, { useEffect, useLayoutEffect, useState } from 'react'
import { ArticleLayout } from './Article'
import { getPage } from './content'
import { DocsHome } from './Home'
import { DocsHeader, DocumentationLayout, type Crumb } from './Layout'
import { pageHref, useRoute } from './router'
import { SearchDialog } from './SearchDialog'
import { Sidebar } from './Sidebar'

const NotFound: React.FC<{ slug: string }> = ({ slug }) => (
  <div className="rd-article rd-notfound">
    <header className="rd-article-head">
      <p className="rd-eyebrow">404</p>
      <h1>Page not found</h1>
      <p className="rd-lede">
        There is no documentation page at <code>{slug}</code>. It may have moved; try search or start from the overview.
      </p>
    </header>
    <p>
      <a className="rd-pill" href="#/">Back to the overview</a>
    </p>
  </div>
)

export const DocsApp: React.FC = () => {
  const route = useRoute()
  const [menuOpen, setMenuOpen] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)
  const page = route.slug ? getPage(route.slug) : undefined

  // keyboard: Cmd/Ctrl+K or "/" opens search
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const typing = /^(INPUT|TEXTAREA|SELECT)$/.test((e.target as HTMLElement)?.tagName ?? '')
      if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setSearchOpen((v) => !v)
      } else if (e.key === '/' && !typing && !searchOpen) {
        e.preventDefault()
        setSearchOpen(true)
      } else if (e.key === 'Escape' && menuOpen) {
        setMenuOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [searchOpen, menuOpen])

  // title, and scroll to the requested section (or the top) after each navigation
  useLayoutEffect(() => {
    document.title = page ? `${page.title} · Runport Docs` : route.slug ? 'Not found · Runport Docs' : 'Runport Docs'
    if (route.section) {
      document.getElementById(route.section)?.scrollIntoView({ block: 'start' })
    } else {
      window.scrollTo(0, 0)
    }
  }, [route.slug, route.section, page])

  // lock page scroll behind the mobile drawer
  useEffect(() => {
    document.documentElement.classList.toggle('rd-lock', menuOpen)
  }, [menuOpen])

  const crumbs: Crumb[] = [{ label: 'Docs', href: pageHref('') }]
  if (page) {
    crumbs.push({ label: page.group })
    crumbs.push({ label: page.title })
  } else if (route.slug) {
    crumbs.push({ label: 'Not found' })
  } else {
    crumbs.push({ label: 'Overview' })
  }

  return (
    <DocumentationLayout
      sidebar={<Sidebar current={route.slug} open={menuOpen} onClose={() => setMenuOpen(false)} onSearch={() => setSearchOpen(true)} />}
      header={<DocsHeader crumbs={crumbs} onMenu={() => setMenuOpen(true)} onSearch={() => setSearchOpen(true)} />}
      overlay={<SearchDialog open={searchOpen} onClose={() => setSearchOpen(false)} />}
    >
      {!route.slug ? <DocsHome /> : page ? <ArticleLayout key={page.slug} page={page} /> : <NotFound slug={route.slug} />}
    </DocumentationLayout>
  )
}
