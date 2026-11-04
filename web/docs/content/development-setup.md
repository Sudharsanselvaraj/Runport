---
title: Development setup
description: Set up a development environment for the Python package and the web frontends.
---

## Python

```bash
git clone https://github.com/Sudharsanselvaraj/runport.git
cd runport
uv sync --extra dev --extra report
```

The core package lives in `src/runport/`, tests in `tests/`, and reference plugins in `examples/plugins/`.

## Linting and types

The CI runs these; run them before you push:

```bash
uv run ruff check
uv run ruff format --check
uv run mypy
```

## Web frontends

The `web/` directory holds three independent Vite + React + TypeScript apps. They share a `package.json` and Node 20.

```bash
cd web
npm install
```

| App | Dev server | Production build | Output |
|---|---|---|---|
| Workbench dashboard | `npm run dev` (port 5173, proxies `/api` to 8000) | `npm run build` | `web/dist/` |
| Landing site | `npm run dev:landing` (port 5174) | `npm run build:landing` | `web/dist-landing/` |
| Documentation | `npm run dev:docs` (port 5175) | `npm run build:docs` | `web/dist-docs/` |

For the dashboard, start the API in another terminal with `uv run runport web`.

The public website serves the documentation at `/docs/`. `npm run build:site` builds the landing page and puts the docs inside it at `web/dist-landing/docs/`, so `web/dist-landing/` is the whole site to deploy. In development, run `npm run dev:docs` alongside `npm run dev:landing`; the landing server proxies `/docs/` to it.

## Editing the documentation

Pages are Markdown files in `web/docs/content/`, one per page, with `title` and `description` front matter. The sidebar order is in `web/docs/app/content.ts`. Link to another page with `/slug` or `/slug#heading`. Callouts use `> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]` and `> [!WARNING]`.

## Never commit

`.env*`, `*.db`, `*.db-wal`, `data/budget_policy.json`, `reports/` or private datasets.
