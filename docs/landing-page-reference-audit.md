# Runport — Landing Page Reference Audit & Technical Inventory
## Reference Website: https://getpulse.framer.website/

This document details the reverse-engineered layout structure, design tokens, typography scale, component proportions, asset inventory, and motion behaviors observed on `https://getpulse.framer.website/`.

---

## 1. Global Page Metrics & Structure
- **Total Measured Height**: 6,979 px (desktop 1440px width)
- **Viewport Tested**: 1440×900, 1280×800, 1024×768, 768×1024, 390×844, 375×812
- **Document Background**: `#070707` (`rgb(7, 7, 7)`) pitch dark
- **Primary Font Family**: `"Inter Display", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
- **Monospace Font Family**: `"Intel One Mono", "SF Mono", Menlo, Consolas, monospace`
- **Max Content Width**: 1,200 px (sections), 1,280 px (hero background frame)
- **Grid System**: 12-column flex/grid with 24px gutter and 24px - 32px card padding

---

## 2. Central Design Tokens & Vocabulary

### Colors
- `bg-canvas`: `#070707` (95% of document background)
- `bg-surface-elevated`: `rgba(18, 18, 22, 0.75)`
- `bg-surface-card`: `rgba(24, 24, 28, 0.6)`
- `bg-glass-pill`: `rgba(255, 255, 255, 0.08)`
- `border-subtle`: `rgba(255, 255, 255, 0.08)`
- `border-glass`: `rgba(255, 255, 255, 0.15)`
- `border-glass-active`: `rgba(255, 255, 255, 0.3)`
- `text-primary`: `#FFFFFF`
- `text-secondary`: `#E8E8E8`
- `text-muted`: `rgba(255, 255, 255, 0.6)`
- `text-dim`: `rgba(255, 255, 255, 0.4)`
- `accent-green`: `#10B981` (active progress, metrics)
- `accent-blue`: `#3B82F6` (projects, connectors)
- `accent-amber`: `#F59E0B` (badges, warnings)
- `accent-cyan`: `#06B6D4` (tasks, replay)

### Radii
- Pill Buttons / Badges / Nav: `9999px`
- Bento Cards / Sections: `20px` to `24px`
- Nested Mockup Panels: `12px` to `16px`

---

## 3. Sequential Section Inventory (Exact Reference Order)

### Section 0: Sticky Navigation
- **Position**: Floating sticky `top: 16px`, centered
- **Dimensions**: Height `52px`, max-width `1080px`, z-index `100`
- **Background**: Translucent frosted glass `rgba(15, 15, 18, 0.75)` with `backdrop-filter: blur(16px)`
- **Border**: `1px solid rgba(255, 255, 255, 0.1)`
- **Items**:
  - Left: Logo mark + Brand name (`14px`, weight 500)
  - Center: Navigation links: "Product", "Pricing", "Updates" (`14px`, weight 400, color `rgba(255, 255, 255, 0.7)`)
  - Right: "Start for free" (pill with subtle border) + "Contact" (solid dark pill)
- **Mobile Behavior**: Collapses to hamburger toggle pill menu at `<768px`.

### Section 1: Hero Section
- **Height**: ~900px (full viewport on 1440x900)
- **Background**: Cinematic painterly dreamscape with peach sunset clouds, giant celestial body, stone architectural arches, and standing observer figure
- **Content Alignment**: Centered
- **Headline**: "Make ideas move." (`42px` - `48px`, weight 500, letter-spacing `-0.03em`)
- **Subtitle**: "A focused workspace for small teams to organize their work, stay aligned, and get things done." (`14px` - `16px`, color `#E8E8E8`, max-width `540px`)
- **CTAs**:
  - Primary 1: "Start for free" (frosted glass pill `rgba(255, 255, 255, 0.12)`, `16px`, weight 500)
  - Primary 2: "See how it works" (dark pill `#0F0F11`, `16px`, weight 500)
- **Social Proof Banner**: "Trusted by teams." with client wordmark logos (Lakewood, Crestline, Harborview, Summit, Northgate) in muted gray opacity.

### Section 2: Statement Callout Banner
- **Height**: ~450px
- **Background**: Pure pitch `#070707`
- **Headline**: "Work shouldn't feel this scattered." (`64px`, weight 600, letter-spacing `-0.03em`, centered)
- **Motion**: Scroll reveal fade-up with gentle opacity transition.

### Section 3: Feature & Product Interface Showcase
- **Height**: ~850px
- **Layout**: Two columns (left copy, right rich software UI mockup)
- **Header**:
  - Left: "See the work. Know what's next." (`42px`, weight 500)
  - Right: Supporting description (`14px`, max-width `420px`)
- **Left Card**:
  - Badge: "02 Build" / "01 Benchmark" (pill with amber border)
  - Title: "Make the work easy to follow." (`22px`, weight 500)
  - Description: "Break projects into manageable tasks..." (`14px`, text-muted)
- **Right Panel**: Detailed software mockup with sidebar navigation, search bar (`⌘K`), active project breadcrumbs, 72% progress bar, metric counters, team member avatars, and detail cards.

### Section 4: Multi-Column Bento Feature Showcase
- **Headline**: "Everything your team needs. Nothing you don't." (`42px`, weight 500, centered)
- **Layout**: 4-column horizontal card showcase with individual ambient tinted glows:
  1. Card 1 (Amber glow): "Projects" — Organize work into focused projects
  2. Card 2 (Blue glow): "Team" — See who's working on what
  3. Card 3 (Emerald glow): "Collaboration" — Share feedback and updates
  4. Card 4 (Cyan glow): "Tasks" — Create, assign, and track
- **Card Styling**: `border-radius: 20px`, dark glass gradient, embedded mini UI visual, icon, title (`18px`), body (`14px`).

### Section 5: Key Metrics & Testimonial Bento
- **Stat Counters**: 4 large figures:
  - `12+` Active projects / Models evaluated
  - `38+` Tasks completed / Workflows connected
  - `94%` Tasks on track / Pass rate
  - `4.8/5` Team satisfaction
- **Bento Card**: Split card:
  - Left: Testimonial quote (`20px`, weight 500), body description, author signature (`Maya Chen, Studio Lead`)
  - Right: Scenic card with overlay stats (`3.2× faster`, `38% less time`, `12k+ teams`).

### Section 6: Unified Brand / Central Platform Showcase
- **Headline**: "One workspace for the way your team works." (`42px`, weight 500, centered)
- **Subtitle**: "PULSE brings planning, collaboration, and progress together in one focused space."
- **Visual**: Atmospheric arches backdrop with prominent 3D metallic brand emblem centered.
- **3-Column Feature Row**:
  - Planning: "Turn ideas into clear projects and priorities."
  - Collaboration: "Share updates, feedback, and decisions where the work happens."
  - Progress: "Know what's moving, what's blocked, and what's ready to ship."

### Section 7: Pricing Section
- **Headline**: "Simple pricing." (`42px`, weight 500, centered)
- **Subtitle**: "Start with what you need. Upgrade when your team grows."
- **Toggle**: Interactive pill toggle ("Monthly" / "Yearly")
- **3 Pricing Cards**:
  - Starter (`$0 / month`): 1 Workspace, 3 Projects, 100 Tasks, Basic Notes
  - Pro (`$19 / month`, Featured): Unlimited Projects, Unlimited Tasks, Notes & Files, Team Collaboration, Integrations
  - Scale / Enterprise (`$49 / month`): Everything in Pro, Unlimited Team, Advanced Permissions, Analytics, Priority Support
- **Footer note**: "No credit card required. · Start free. · Upgrade anytime."

### Section 8: FAQ Section
- **Headline**: "Questions, answered." (`42px`, weight 500)
- **Left Subtext**: "Everything you need to know before getting started." + "Didn't find what you're looking for?" + "Talk to us" pill button.
- **Right Accordion**: 6 collapsible dark pill cards with smooth height expansion and chevron animation.

### Section 9: Final Call-to-Action (CTA)
- **Graphic**: 3D embossed metallic brand emblem centered
- **Headline**: "Make the next move." (`42px`, weight 500)
- **Subtitle**: "Bring your projects, your team, and your next idea into one focused workspace."
- **CTA**: "Start for free" (pill button)

### Section 10: Footer
- **Layout**: Clean grid with Brand Logo, Mission statement, Social icon row (X, Instagram, Telegram) on left; Product, Resources, Legal link columns on right.
- **Copyright**: `© 2026 Runport. All rights reserved.`
