# Documentation Portal: Build and Validation

The Runport documentation portal is a separate static site that sits next to the
landing page and the local Workbench. Its layout follows Linear Docs
(https://linear.app/docs). Its type, colour and shape come from the Runport
landing page tokens.

## 1. Location and builds

| | Value |
|---|---|
| Entry | `web/docs/index.html` → `web/docs/main.tsx` |
| App code | `web/docs/app/` |
| Content | `web/docs/content/*.md` (one Markdown file per page, with `title` and `description` front matter) |
| Sidebar order | `NAV` in `web/docs/app/content.ts` |
| Dev server | `npm run dev:docs` (http://127.0.0.1:5175) |
| Build | `npm run build:docs` → `web/dist-docs/` (static and relative: `base: './'`) |
| Routing | Hash routes: `#/slug`, and `#/slug#heading` for a section, so it works on any static host without rewrites |
| Marketing link | `VITE_SITE_URL` at build time (default `/`) |

The portal never imports the landing page or the Workbench, and it never calls
the Runport API. It adds no new dependencies: it uses React and lucide-react,
which the project already has. Markdown is read by a small built-in parser
(`web/docs/app/markdown.ts`).

### Components

These are in `web/docs/app/`:

- `DocumentationLayout`, `DocsHeader` and `Breadcrumbs`: `Layout.tsx`
- `Sidebar`, `SidebarGroup` and `SidebarLink`: `Sidebar.tsx`
- `ArticleLayout`, `TableOfContents`, `CodeBlock`, `Callout` and `Pagination`: `Article.tsx`
- `DocsHomeCard`: `Home.tsx`
- `SearchDialog`: `SearchDialog.tsx`
- The search index: `content.ts`

## 2. Design tokens reused from the landing page

These values are copied under the same `--rp-*` names, so the portal and the
landing page stay in step:

- **Colours:**
  - canvas `#070707`, control `#111111`, text `#e8e8e8`
  - muted `rgba(255,255,255,.4)`, glass `.06`, line `.08`
  - accent `#ff6600`, used only for warnings and search highlights
- **Type:**
  - fonts: Inter (opsz axis) and Intel One Mono
  - tracking −0.02em
  - sizes: home H1 42/500, article H1 32/500, H2 20/500, H3 16/500, prose 16/1.7, UI 14, captions 12
- **Shape:** 12px cards, 120px pills

The portal adds three tokens of its own:

- `--rd-secondary` (`rgba(255,255,255,.58)`), for long descriptions. Muted .4 is too low-contrast for paragraph text.
- 13px for the contents rail and code.
- The reading layout sizes.

## 3. Layout compared with Linear Docs (1440 × 900)

| Measurement | Linear Docs | Runport Docs |
|---|---|---|
| Sidebar width | 280 | 280 |
| Header height | 64 | 64 |
| Content left edge | 372 | 372 |
| Home H1 top | 112 | 112 |
| Home column width | 976 | 976 |
| Home cards | 4 per row, 16 gap, 242 × 280 | 4 per row, 16 gap, 232 × 215 (no icon panel) |
| Article column | 650 | 680 (16px prose ≈ 75 characters per line) |
| Contents rail | x 1098, 250 wide | x 1128, 220 wide |
| Sidebar rows | group 36, page 32 | group 36, page 32 |
| Article H1 / H2 / H3 | 32 / 24 / 20 (590 weight) | 32 / 20 / 16 (500 weight, Runport scale) |
| Body | 15/24, #d0d6e0 | 16/27, #e8e8e8 |

Breakpoints:

- At 1199px and below, the contents rail becomes an inline "On this page" disclosure.
- At 1023px and below, the sidebar is 248px and the inset is 40px.
- At 860px and below, the sidebar becomes a drawer opened from the header.
- At 600px and below, cards stack, there are 20px gutters, and search shows as an icon only.

Side-by-side captures are in `artifacts/docs/pair_{home,article}_{1440x900,390x844}.png`.
The `artifacts/` folder is not committed (it is in `.gitignore`).

## 4. Checks (headless Chrome, DPR 1)

Every check below passed:

- **Every viewport** (1440, 1366, 1024, 768, 390, 375), home and article pages:
  - no horizontal overflow
  - no images or background images
  - no SVG except interface icons inside controls
  - no console errors
- **Sidebar:** groups expand and collapse (`aria-expanded`), and the current page is highlighted.
- **Navigation:**
  - Home cards open the right article.
  - The breadcrumb reads "Docs / group / page", and "Docs" returns home.
  - Next and Previous follow the sidebar order.
  - Links in the contents rail scroll to their heading (top at 88px, below the sticky header) and highlight it.
  - A refresh on `#/datasets#splits` keeps the page, the section and the sidebar highlight.
- **Search:**
  - Opens with Cmd/Ctrl+K, `/` or the button.
  - Returns real pages and sections for "reconcile", "wilson interval", "ollama", "privacy gate" and "RUN LIVE".
  - Shows an empty state for an unknown term.
  - Arrow keys plus Enter open the result; Escape closes.
- **Links and routes:**
  - An unknown route shows a not-found page.
  - All 54 entries in the sidebar render (53 pages plus Overview).
  - All 114 internal links and their section anchors resolve (checked statically).
  - No link points to localhost.
- **Mobile (390):** the drawer opens; choosing a page navigates and closes the drawer.
- **Builds:** `npm run build`, `build:landing` and `build:docs` all pass.
- **Code snippets:** the snippets were run against the package and their outputs match the pages. One example output was corrected (`FieldMatchScorer`).

## 5. How the content was sourced

Every page was written from the repository, not from the older `docs/*.md`
files. CLI options come from `runport <command> --help`. Defaults come from
`core/workspace.py`. Connector parameters come from their constructors. Guard
behaviour comes from `runs/executor.py`, and scoring from `evaluation/evaluator.py`
and `runport.scorers`.

Where the older docs disagreed with the code, the code wins. For example,
`runport init` creates `data/runport.db`, not `.runport/`.

## 6. Gaps and product findings

The pages describe these behaviours as they are, without hiding them. They are
listed here because they may need product work rather than documentation:

1. **CLI replay summary is fixed.** `runport benchmark --replay` stores fixed summary values (accuracy 1.0, latency 110 ms). It checks the pipeline but does not measure a model.
2. **Placeholder scores for unlabelled cases.** For a case with no `expected_answer`, the live CLI heuristic records fixed accuracy 0.70 and groundedness 0.75, rather than leaving them empty. This conflicts with the "null is not 0" spirit.
3. **`GenericRunner` scores are completion rates.** It stores accuracy, groundedness and overall as 1.0 or 0.0 by case status, so they measure completion, not correctness.
4. **`benchmark-rag` cannot run on a fresh clone.** It needs `data/audit/parsed_records_*.jsonl` and points to a `runport audit-kb` command, but that command does not exist and the files are not shipped.
5. **`smoke-test --live` sends nothing.** It asks for approval and then sends no requests.
6. **`annotate` is read-only.** It lists verification status but does not edit labels.
7. **`targets:` in `runport.yaml` is not used by the CLI.** It is validated, but no CLI command reads it. Providers other than OpenRouter are set up in Python.
8. **No dedicated adapters for some providers.** There is no vLLM-specific adapter (it is documented through `openai_compat`), no throughput metric, and no separate "experiment" object. The requested "Throughput" page was left out, and "Experiments" is documented as "Runs and plans".
9. **The REST API is not documented.** It is not covered yet.
