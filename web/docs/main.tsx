// Entry for the documentation portal. Independent of the landing page and of
// the local Workbench (src/App.tsx); it makes no network calls of its own.
import React from 'react'
import ReactDOM from 'react-dom/client'
import { DocsApp } from './app/DocsApp'
import './app/docs.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <DocsApp />
  </React.StrictMode>,
)
