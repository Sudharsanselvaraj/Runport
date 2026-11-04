// Entry for the public marketing site. It renders only the landing page and
// never imports the Workbench (src/App.tsx), which runs locally via `runport web`.
import React from 'react'
import ReactDOM from 'react-dom/client'
import { LandingPage } from '../src/components/landing/LandingPage'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <LandingPage />
  </React.StrictMode>,
)
