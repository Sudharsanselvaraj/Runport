// External destinations used by the portal chrome. Nothing here points at a
// local server: the docs are a static site and never call the Runport API.
export const REPO_URL = 'https://github.com/Sudharsanselvaraj/runport'
export const ISSUES_URL = `${REPO_URL}/issues`

// The marketing site. Set VITE_SITE_URL at build time when the docs are served
// from a different host than the landing page (default: the same host's root).
export const SITE_URL: string = (import.meta.env.VITE_SITE_URL as string | undefined) || '/'

export const EDIT_BASE = `${REPO_URL}/blob/main/web/docs/content`
