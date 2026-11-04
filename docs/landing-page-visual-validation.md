# Landing Page Visual Validation

Reference: https://getpulse.framer.website/. Measurements and method are in
[landing-page-reference-audit.md](landing-page-reference-audit.md).

Validated on 2026-11-04 against `npm run dev` (Vite, 127.0.0.1:5173) with
headless Chrome over CDP, DPR 1, using the same viewports and scroll positions
as the reference capture. Evidence lives in `artifacts/compare/` (gitignored):

- `pair_<section>.png`: reference (left) and Runport (right) at 1440 × 900, same scroll offset.
- `<section>_reference.png`, `<section>_runport.png`: the full-size frames.
- `positions.md`: the measured position and type table below.
- `runport_390x844_s*.png`, `runport_1024x768_s*.png`, `menu_*.png`: responsive frames.

## 1. Measured position and typography (1440 × 900)

y is the element's document-space top in px. Type is size/weight and computed letter-spacing.

| Element | Ref y | Runport y | Δy | Ref type | Runport type |
|---|---|---|---|---|---|
| Nav brand | 14 | 14 | 0 | 14/500, -0.28px | 14/500, -0.28px |
| Hero H1 | 381 | 377 | -4 | 42/500, -0.84px | 42/500, -0.84px |
| Hero sub | 431 | 435 | +4 | 14/400, -0.28px | 14/400, -0.28px |
| Statement | 1286 | 1286 | 0 | 64/600, -1.28px | 64/600, -1.28px |
| Showcase heading | 1800 | 1800 | 0 | 42/500, -0.84px | 42/500, -0.84px |
| Step tag | 1936 | 1948 | +12 | 12/500, -0.24px | 12/500, -0.24px |
| Step title | 1992 | 2008 | +16 | 20/500, -0.2px | 20/500, -0.2px |
| Carousel H2 | 3160 | 3160 | 0 | 32/500, -0.64px | 32/500, -0.64px |
| Stat label | 3838 | 3820 | -18 | 14/400 | 14/400 |
| Proof quote | 3943 | 3941 | -2 | 20/500, -0.2px | 20/500, -0.2px |
| Platform H2 | 4490 | 4482 | -8 | 32/500, -0.64px | 32/500, -0.64px |
| Pricing H2 | 5245 | 5243 | -2 | 32/500, -0.64px | 32/500, -0.64px |
| FAQ H2 | 5916 | 5936 | +20 | 32/500, -0.64px | 32/500, -0.64px |
| Final CTA H2 | 6528 | 6548 | +20 | 32/500, -0.64px | 32/500, -0.64px |
| Copyright | 6945 | 6978 | +33 | 12/500, -0.24px | 12/500, -0.24px |
| **Page height** | **6979** | **7017** | **+38** | | |

Before this work the same table showed a 54 px hero H1 on two lines, 44 px H2s,
a 68 px statement with -2.72px tracking, a 1152 px column, and a page of
7582 px (+603).

## 2. Section by section

| Section | Mismatch found | Correction | Remaining | Result |
|---|---|---|---|---|
| Navigation | 70 px floating bordered capsule; Inter Display never loaded | Full-bleed 48 px bar, 6 % glass + blur(5px), 800 px row, 32 px pills; Inter (opsz axis) loaded | None measurable | Match |
| Hero | 54 px two-line H1; static; art over-cropped | Template painting at the reference crop (full-bleed, 0→100 % shade); 42 px single line; blur-rise entrance; 2.3 s settle; 0.7× parallax | None measurable | Match |
| Hero foot | Invented customer logos copied from the template | Marquee of real integration targets, serif wordmarks | None | Match (structure) |
| Statement | 68 px, over-tight tracking, three lines | 64/600, -0.02em, two lines, per-word blur rise | None | Match |
| Showcase | Static two-column block, one step | Sticky stage pinned at top 40, four steps crossfade card copy and mockup, mask fades as measured | Steps advance every 100 px (reference ~150 px); a clickable step list is added | Close |
| Carousel | Four static cards, 44 px H2 | Six 282 × 355 tiles, radial tints, draggable track with spring snap and dots, 32 px masked H2 | Tile thumbnails are live HTML mockups rather than screenshots | Match (geometry) |
| Metrics | 56 px Inter; invented values (99.8 %, 4.9/5) | Intel One Mono 48 px, count-up, product facts only | None | Match (geometry) |
| Proof card | 1100 px wide; invented testimonial | 700 × 330 split card quoting invariant #1, image with three verifiable facts | None | Match (geometry) |
| Platform | 1152 px column, oversized type, extra top margin | Full-bleed painting with fades, 32 px H2, mark with fade mask, 700 px pillar row, no margin | Mark is Runport's flat emblem, not a 3D-extruded logo | Close |
| Pricing | The template's exact $0 / $19 / $49 for plans that do not exist | Three real $0 ways to run Runport; the toggle switches the replay and live spend note; mono 42 px prices; image panels | None | Match (geometry) |
| FAQ | 44 px H2, wider rows | 403 px column + accordion, 64 px row pitch, height-auto expand, rotating icon | None | Match |
| Final CTA | Pill rendered as bare text | Fixed reset specificity (`:where()`) so `.rp-pill` styles apply | None | Match |
| Footer | Oversized, loose | 1200 px row, 14 px columns with icons, 12 px legal line | +33 px cumulative offset | Close |

## 3. Motion (measured on Runport, same probe as the reference)

| Behaviour | Reference | Runport |
|---|---|---|
| Hero H1 entrance | 0 → 1 opacity, y 40 → 0, blur 10 → 0, ~0.8 s, 50 % at ~35 % | Same curve: 0.61 opacity at 0.49 s into the run, settled by 1.0 s |
| Hero sub stagger | +0.12 s | +0.12 s |
| Hero art settle | y -45 → 0 over ~2.3 s | y -45 → 0, scale 1.04 → 1 over 2.3 s |
| Hero parallax | art moves 105 px per 150 px of scroll (0.7×) | 105 px per 150 px (0.7×) |
| Showcase pin | header held at top 40 for ~450 px | held at top 40 for 400 px; step changes at +150, +250, +350 |
| Reduced motion | n/a | With `prefers-reduced-motion: reduce`: no transforms or blur, marquee stopped, parallax off (verified via CDP media emulation) |

## 4. Responsive and quality checks

| Viewport | Horizontal overflow | Broken images | Console errors | Mobile menu |
|---|---|---|---|---|
| 1440 × 900 | none | 0 | 0 | n/a |
| 1366 × 768 | none | 0 | 0 | n/a |
| 1280 × 800 | none | 0 | 0 | n/a |
| 1024 × 768 | none | 0 | 0 | n/a |
| 768 × 1024 | none | 0 | 0 | opens |
| 390 × 844 | none | 0 | 0 | opens |
| 375 × 812 | none | 0 | 0 | opens |

Below 810 px the layout switches to the phone arrangement (as the reference
does): 20 px gutters, a 38 px balanced H1, a stacked showcase with each step's
mockup inline, 2 × 2 stats, and stacked pricing, FAQ and footer.

Regression: `npm run build` succeeds (tsc + vite); `uv run pytest`: 373 passed;
the Workbench (`npm run build`, served by `runport web`) opens straight on Setup
and no longer contains the landing page.

## 5. Separate builds

The landing page is the public website and is built on its own; the Workbench is
the local app. Neither links to the other.

| | Public landing site | Local Workbench |
|---|---|---|
| Entry | `web/landing/index.html` → `landing/main.tsx` | `web/index.html` → `src/main.tsx` |
| Dev | `npm run dev:landing` (127.0.0.1:5174) | `npm run dev` (127.0.0.1:5173, proxies `/api`) |
| Build | `npm run build:landing` → `web/dist-landing/` | `npm run build` → `web/dist/` |
| Assets | `web/landing/public/` | `web/public/` |
| Calls `/api` | never | yes |

Landing calls to action point to GitHub (`Get started` → the README quickstart,
`Star on GitHub`), never to the dashboard.

## 6. Known differences

1. **Artwork is the template's own.** At the owner's request, the hero, platform,
   pricing and proof images are the Pulse template's files
   (`web/landing/public/assets/landing/hero-bg.png`, `testimonial-bg.jpg`,
   `pricing-1/2/3`). They belong to the template author, so publishing them
   requires the template licence. `scripts/generate_landing_art.py` can still
   produce original replacements.
2. **Content is Runport's, not the template's.** Different words change line
   lengths, so a few blocks sit up to ±20 px from the reference (and the footer
   +33 px).
3. **Fonts load from Google Fonts**, as before. For a local-first tool,
   self-hosting the three OFL-licensed families would remove that external
   request.
4. **Step cadence.** The sticky showcase steps every 100 px rather than ~150 px,
   so the four steps fit a shorter pin with the same section height as the reference.
