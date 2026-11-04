# Landing Page Reference Audit

Reference: https://getpulse.framer.website/ (Framer template "PULSE").
Target: the Runport public landing page (`web/src/components/landing/*`).

Captured on 2026-11-04 with headless Chrome over CDP (DPR 1). Every value
marked **M** was read from computed styles or `getBoundingClientRect()` on the
live page. Values marked **E** are visual estimates from screenshots. Raw
dumps live next to the screenshots in `artifacts/reference/` (gitignored, so
third-party captures are not published with the repo):

- `pulse_<W>x<H>.json`: every visible text node (rect, font, size, weight,
  line-height, tracking, colour) and every image or background layer.
- `pulse_<W>x<H>_sNN.png`: viewport slices taken every viewport height.
- `anim_entrance.json`, `anim_scroll.json`: motion samples (see section C).
- `surfaces.txt`: ancestor chains with background, border, radius, blur, mask
  and padding for 20 key components.
- `artifacts/before/`: the same capture of the Runport page before this work.

Scope and licensing: we match layout, proportion, typography, surfaces and
motion. We do not reuse the template's logo, copy, testimonial
names or invented metrics. At the owner's request the template's raster art
is used as-is (hero, platform, pricing and proof images), which requires the
template licence before publishing. Copy, logo row, testimonial and prices are
Runport's own.

---

## A. Section inventory (desktop 1440 × 900, page height 6979 px **M**)

| # | Section | Top y | Height | Notes |
|---|---|---|---|---|
| 0 | Fixed nav bar | 0 (fixed) | 48 | full-bleed bar, inner row 800 px wide |
| 1 | Hero | 0 | 900 | full-bleed painting, centred copy, "Trusted by" marquee at y 843 |
| 2 | Statement | 900 | ~750 | one 64 px line pair at y 1286, art glow strip at its foot (y 1654) |
| 3 | Sticky product showcase | ~1650 | ~1450 | header + step card + product mockup; header pins at top 40 |
| 4 | Feature carousel | 3060 | 620 | H2 + 6 cards (282 × 355) in a draggable 2-page track with dots |
| 5 | Metrics + proof | ~3700 | ~550 | 4 mono stats, then a 700 × 330 split card (quote + image) |
| 6 | Platform | 4245 | 900 | full-bleed painting again (scaled 1.1), H2, 3D mark, 3 pillars |
| 7 | Pricing | 5145 | 671 | H2 + toggle + 3 cards (323 wide) with an image panel inside |
| 8 | FAQ | 5916 | 370 | 403 px left column + accordion on the right |
| 9 | Final CTA | 6285 | 445 | mark, H2, line, one button |
| 10 | Footer | ~6730 | ~250 | 1200 px wide row: brand + socials, 3 link columns, legal line |

## B. Visual measurements

### Layout grid **M**

| Token | 1440 | 1024 | 390 |
|---|---|---|---|
| Content column | 1000 px (x 220–1220) | 944 px (x 40–984) | 350 px (x 20–370) |
| Section padding | `100px 60px 0` | `100px 40px 0` **E** | `80px 20px 0` **E** |
| Nav inner row | 800 px (x 320–1120) | 784 px **E** | full width, 20 px gutter |
| Footer row | 1200 px (x 120–1320) | 944 px | 350 px |
| Narrow column (metrics, proof, pillars) | 700 px (x 370–1070) | 700 px | 350 px |

### Typography **M**

Fonts loaded: `Inter Display` 400/500/600 and `Intel One Mono` 400.
`Inter Display` is Inter's display optical size. Google's Inter variable font
exposes the `opsz` axis, so with `font-optical-sizing: auto` it renders the same
cut at large sizes.

| Role | Size / weight | Line height | Tracking | Colour |
|---|---|---|---|---|
| Hero H1 | 42 / 500 (40 at 1024, 38 at 390) | 1.0 | -0.02em (-0.84px) | #fff |
| Statement | 64 / 600 (all breakpoints) | 1.0 | -0.02em | #fff |
| Showcase H1 | 42 / 500 | 1.0 | -0.02em | #fff, tail words faded |
| Section H2 | 32 / 500 | 1.2 | -0.02em | #fff, mask fade to the right |
| Card title (H3) | 20 / 500 | 1.2 | -0.01em | #fff |
| Small title | 16 / 500 | 1.4 | -0.02em | #fff |
| Body | 14 / 400 | 1.2 | -0.02em | #e8e8e8 |
| Nav link | 14 / 400 | 1.2 | -0.02em | #e8e8e8 |
| Button label | 16 / 500 | 1.4 | -0.02em | #fff |
| Tag / caption | 12 / 500 | 1.0 | -0.02em | #ff6600 on rgba(255,102,0,.12) |
| Stat value | Intel One Mono 48 / 400 | normal | 0 | #fff |
| Stat label | 14 / 400 | 1.2 | 0 | rgba(255,255,255,.4) |
| Price | Intel One Mono 42 / 400 | 1.0 | -0.02em | #fff |

The heading-fade effect is `mask-image: linear-gradient(270deg, transparent -13%, #000 76%)`
on the H2 wrapper, so the last word or two of every H2 falls off toward grey. **M**

### Surfaces **M**

| Element | Size | Background | Radius | Effects |
|---|---|---|---|---|
| Nav bar | 1440 × 48, pad 8 | rgba(255,255,255,.06) | 0 | backdrop blur(5px) |
| Glass pill button | 32 h (nav), 38 h (hero), pad 8 × 16 | rgba(255,255,255,.06) | 120 | blur(5px) |
| Dark pill button | same | #111111 | 120 | blur(5px) |
| Light pill (toggle / floating) | 24 h | #ffffff, text #070707 | 41 | none |
| Toggle track | 145 × 32, pad 4, gap 4 | #111111 | 100 | none |
| Step card (showcase) | 315 × 702, pad 24, gap 40 | rgba(255,255,255,.06) | 12 | blur(3px), mask `linear-gradient(#000 81%, transparent)` |
| Product mockup | 669 × 698 at x 549 | image | 10 | right edge bleeds past the column, fades out |
| Carousel card | 282 × 355, pad 16, gap 12, step 298 | radial-gradient(50% 50% at 50% 54.5%, dark core → tinted rim) | 16 | blur(3px); image 275 × 230, radius 8/0 top |
| Proof card | 700 × 330, pad 4 | rgba(255,255,255,.06) | 12 | mask fades the bottom 19% |
| Pricing card | 323 × 330–400, pad 16 | rgba(255,255,255,.06) | 12 | mask fades the bottom 19%; image panel 291 × 169–223 |
| FAQ row | ~577 × 40 **E** | rgba(255,255,255,.06) **E** | 8 **E** | none |
| Step tag | 55 × 20, pad 4 × 8 | rgba(255,102,0,.12) | 114 | none |

Carousel card rim tints **M**: olive `radial-gradient(rgb(18,15,4) → rgb(110,110,77))`
and teal `radial-gradient(rgb(2,15,15) → rgb(61,87,87))`, alternating.

### Colour tokens **M**

`#070707` canvas, `#111111` dark control, `#e8e8e8` body, `#ffffff` headings,
`rgba(255,255,255,.06)` glass, `rgba(255,255,255,.4)` muted labels, `#ff6600`
accent (tags only). The painting supplies all other colour; the UI itself is
monochrome plus one orange accent.

### Backgrounds and gradients

- Hero: full-bleed painting with `object-fit: cover`, plus a
  `linear-gradient(transparent 0%, #070707 100%)` layer over the full 900 px. **M**
- Statement foot: a 1331 × 298 crop of the painting under heavy top and bottom
  fades makes a horizon glow that the showcase header sits on. **M**
- Metrics: a 793 × 188 crop of the painting glows behind the stat row. **M**
- Platform: the painting again at 1584 × 990 (110 %), fading to the canvas at the top and bottom. **M** / **E**
- Everything else is flat `#070707`.

### Responsive behaviour **M**

- At 1024 the column switches to 40 px gutters. The showcase stacks its header,
  but the card and mockup stay side by side. Pricing stays at 3 columns.
- At 390 the gutter is 20 px. The statement wraps to four lines and stays 64 px.
  The stats become a 2 × 2 grid, the proof card stacks with its image second, and
  pricing, FAQ and footer stack. Page height is 8007 px.

## C. Animation inventory

Sampled every 90 ms after navigation (`anim_entrance.json`) and every 150 px of
scroll (`anim_scroll.json`). **M** unless noted.

| Element | Trigger | From → to | Duration / delay | Easing |
|---|---|---|---|---|
| Hero H1 | load | opacity 0, y +40, blur 10px → 1, 0, 0 | ~0.8 s, starts ~0.5 s after first paint | ease-out (50 % done at ~35 % of time) |
| Hero sub | load | same as H1 | ~0.8 s, +0.12 s stagger | same |
| Hero CTAs | load | y +40 → 0 (opacity stays 1) | ~0.8 s, with H1 | same |
| Trusted row | load | y +20 → 0 | ~0.9 s, +0.4 s | same |
| Hero painting | load | y −45 → 0 (slow settle) | ~2.3 s | long ease-out |
| Hero painting | scroll | moves at 0.7 × scroll (parallax) | continuous | linear |
| Statement | scroll into view | normal flow, no pin | n/a | n/a |
| Showcase header | scroll | `position: sticky`, top 40, pinned for ~450 px | n/a | n/a |
| Showcase step | scroll | 01 → 02 → 03 → 04 every ~150 px while pinned; card text and mockup crossfade | ~0.4 s **E** | ease-out **E** |
| Carousel | drag / dots | translateX by one page (2 pages) | ~0.5 s **E** | spring **E** |
| Stat numbers | into view | digits roll / count up (rendered as split glyphs, e.g. `12 +`) | ~1 s **E** | ease-out **E** |
| Section blocks | into view | opacity 0, y +40, blur 10px → visible (Framer "appear") | ~0.8 s **E** | same as hero |
| Buttons | hover | background lightens | ~0.2 s **E** | ease **E** |
| FAQ row | click | height auto, chevron rotates | ~0.3 s **E** | ease-out **E** |
| Pricing toggle | click | white thumb slides | ~0.3 s **E** | spring **E** |

No continuous ambient motion; nothing animates once the page has settled.

## D. Screenshot evidence

`artifacts/reference/pulse_1440x900_s00.png` … `_s07.png`,
`pulse_1024x768_s*.png`, `pulse_390x844_s*.png`. The current Runport capture
before this work is in `artifacts/before/runport_1440x900_s*.png`.

## E. Runport (before this work) vs reference

Measured at 1440 × 900 (`artifacts/before/runport_1440x900.json`).

| Area | Reference | Runport before | Required correction |
|---|---|---|---|
| Fonts | Inter Display + Intel One Mono loaded | "Inter Display" declared but never loaded, so Inter is used; no mono | Load Inter (opsz axis) + Intel One Mono, turn on optical sizing |
| Column | 1000 px | 1152 px (x 144–1296) | `--rp-col: 1000px`, 60 px section gutters |
| Navigation | 48 px full-bleed bar, glass 6 % + blur 5, 800 px row, 32 px pills | 70 px floating rounded capsule with a border | Rebuild as a flat bar |
| Hero H1 | 42 / 500, 400 px wide, one line | 54 / 500, two lines (732 px block) | 42 px, single line, 400 px box |
| Hero art | painting with 0.7 × parallax and a load settle | template's painting copied verbatim, static | Original Runport painting, parallax + settle |
| Hero foot | "Trusted by" + logo marquee | invented customer logos (copied names) | Real integration targets as a marquee; no customer claims |
| Statement | 64 / 600, 2 lines | 68 / 600, `-2.72px` tracking | 64 / 600, -0.02em |
| Showcase | sticky header, step card cycles 01–04 with mockup swap | static, single step, mockup 2 col | Sticky scroll scene, 4 Runport steps, 4 mockups |
| Section H2 | 32 / 500 with right-fade mask | 44 / 500, no mask | 32 px + mask |
| Cards | 282 × 355 carousel, radial tint, image + caption | 4 static 293 px cards with fake mini UIs | 6-card draggable carousel with Runport mockups |
| Metrics | mono 48 px, count-up | 56 / 600 Inter; values invented (99.8 %, 4.9/5) | Mono 48, count-up, verifiable product facts only |
| Proof card | 700 × 330 split card | 1100 px wide, invented testimonial ("Maya Chen", the template's name) | 700 px, quote an actual design invariant instead of a fabricated customer |
| Platform | painting + 3D mark + 3 pillars (700 px) | present but 1152 px wide, oversized type | Narrow to 700 px, 32 px H2 |
| Pricing | $ in mono 42, image panel, toggle | the template's exact prices ($0 / $19 / $49) for plans that do not exist | Runport is Apache-2.0: three $0 ways to run it; toggle switches replay vs live spend |
| FAQ | 403 px left, accordion right, 32 px H2 | 44 px H2, wider rows | 32 px H2, proportions as measured |
| Footer | 1200 px row, mono-weight columns | close, oversized | Align to 1200 row, 14 px links |
| Motion | blur-rise entrances, parallax, sticky steps | basic fade-ups only | Implement measured curves; respect `prefers-reduced-motion` |
