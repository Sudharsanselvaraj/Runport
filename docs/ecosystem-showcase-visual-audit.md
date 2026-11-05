# Ecosystem showcase visual audit

Section: "Keep your stack. Runport benchmarks it." on the public landing page.
Component: `web/src/components/landing/BenchmarkFlow.tsx`. Logos and routes come from
`web/src/data/ecosystem.ts`, and the sample run comes from `landingContent.stackFlow`.

## History

| Version | Composition | Problem |
| --- | --- | --- |
| v2 | Dense directory beside the engine, six curved connectors | Tiny pills, crossing lines |
| v3a | Three stacked panels: 46 bordered chips, engine, large results | Read as a dashboard; badges, counts and notes everywhere; very tall |
| v3b | Four illustrated feature cards plus an execution and results row | Clean, but lost the "one pipeline" story |
| **v4 (current)** | Three connected layers on one spine | — |

## Current composition: connected layers

Three layer cards of equal width (1080px), joined by a single vertical spine with ports. Each layer
has the same header: a numbered tag, a title and one sentence.

1. **01 Connect.** All six categories from `ecosystem.ts` (model providers, local inference,
   workflows and agents, evaluation and scoring, data and traces, execution and infra), on a 3×2
   grid with no inner borders. Each category shows its name, one row of overlapping logo discs (up
   to six, then "+N"), and a single muted line such as "OpenAI, OpenRouter and 9 more". There are no
   per-item chips, counts, `EXP` badges or route notes. Each disc's tooltip shows how Runport reaches
   it, for example "Anthropic · via OpenRouter" or "LangGraph · experimental connector".
2. **02 Execute.** The Runport engine as one slim layer: a state pill (Ready, Executing, Run
   complete) and the nine-stage lifecycle on one track, with the seven runner guards bracketed and
   marked "fail closed". The stage labels are sentence case.
3. **03 Compare.** One sample-run window: a progress bar, a six-case timeline (status dot, latency
   bar, duration), and a Run A / Run B table (accuracy, p95 latency, cost with its ESTIMATED or
   UNAVAILABLE basis, invalid output). A footer line reads "Agreement κ … model consensus, not
   accuracy".

## Motion

- The logo discs slide in, staggered by category.
- When the engine reaches the viewport, the sample run plays once:
  1. a signal drops down the spine;
  2. the engine border lights and its ring turns while it runs;
  3. the stages light in order;
  4. a signal drops to Compare;
  5. the case rows and latency bars reveal, then the comparison rows.
- After the run, every 3.4s while the section is on screen, the next category lights up, a signal
  travels down the spine, a highlight sweeps the lifecycle, and the engine glows.
- **Reduced motion:** the finished state shows at once with no loops (verified: discs visible, 6 rows,
  4 metrics, 9 stages lit, no ring).
- **Performance:** worst frame 17ms over 300 frames.

## Size

| Width | v3a (stacked panels) | v3b (feature cards) | v4 (now) |
| --- | --- | --- | --- |
| 1440 | about 2,200px | 1,939px | 1,607px |
| 1024 | about 2,700px | 2,415px | 1,602px |
| 390 | about 3,700px | 3,328px | 2,638px |

## Validation

- `npx tsc`, `npm run build`, `npm run build:landing` and `npm run build:site` pass.
- At 1440, 1280, 1024, 768, 390 and 375: no horizontal overflow, broken images or console errors, no
  truncated category lines, and the comparison table fits its window.
- Screenshots: `artifacts/showcase/v4/`; earlier versions are in `before/`, `after/` and `v3/`.

## Responsive behaviour

- **Below 1024px:**
  - categories go to two columns;
  - each layer's description moves under its title;
  - the results window stacks the timeline above the comparison.
- **Below 810px:**
  - categories go to one column;
  - the lifecycle becomes a vertical list with a connecting rail;
  - the spine shortens to 48px.
- **Below 400px:** the comparison table tightens its padding and type.

## Remaining limitations

- LocalAI, LiteLLM, Helicone, DeepEval and Ragas use monograms; no reliable logo was available.
- Some marks (Mistral, DeepSeek, LangGraph, LangChain) are low-contrast on dark discs.
- The later "Built for the loop" section (`StackCards.tsx`) also shows a logo orbit. It overlaps with
  layer 01 thematically.
