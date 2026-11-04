// Hash routing: `#/slug` opens a page, `#/slug#heading` opens it at a section.
// Hash routes survive a refresh on any static host without server rewrites.
import { useEffect, useState } from 'react'

export interface Route {
  slug: string // '' is the docs home
  section?: string
}

export function parseHash(hash: string): Route {
  const h = hash.replace(/^#/, '')
  if (!h.startsWith('/')) return { slug: '', section: h || undefined }
  const [path, section] = h.slice(1).split('#')
  return { slug: decodeURIComponent(path.replace(/\/$/, '')), section: section ? decodeURIComponent(section) : undefined }
}

export const pageHref = (slug: string, section?: string) => (slug ? `#/${slug}${section ? `#${section}` : ''}` : '#/')

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseHash(window.location.hash))
  useEffect(() => {
    const on = () => setRoute(parseHash(window.location.hash))
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return route
}

export function navigate(slug: string, section?: string) {
  window.location.hash = pageHref(slug, section)
}
