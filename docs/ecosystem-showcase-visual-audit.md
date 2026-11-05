# Ecosystem showcase visual audit

Section: "Keep your stack. Runport benchmarks it." on the public landing page.
Component: `web/src/components/landing/BenchmarkFlow.tsx`. Logos and routes come from
`web/src/data/ecosystem.ts`, and the sample run comes from `landingContent.stackFlow`.

## History

| Version | Composition | Outcome |
| --- | --- | --- |
| v2 | Dense directory beside the engine, six curved connectors | Tiny pills, crossing lines |
| v3a | Three stacked panels with 46 bordered chips | Read as a dashboard; very tall |
| v3b | Four illustrated feature cards | Clean, but lost the pipeline story |
| v4 | Three connected layer cards on one spine | Clean; the categories stayed abstract |
| **v5 (current)** | Integrations panel, then Runport, then a sample trace, then metrics, joined by dashed brackets | — |

## Current composition

1. **Integrations panel.** One bordered panel with corner handles and three columns:
   - **Model providers:** a 4×2 grid of tiles (OpenAI, OpenRouter, Anthropic, Gemini, Mistral,
     DeepSeek, Groq, Together).
   - **Workflows:** a 2×2 grid (Dify, LangGraph, LangChain, n8n).
   - **Local and runtime:** Ollama, vLLM and Python, plus one wide tile, "Any OpenAI-compatible
     endpoint".

   Tiles are 86px squares with a logo and a short name. Each tile's tooltip shows how Runport reaches
   it, for example "Anthropic · via OpenRouter" or "LangGraph · experimental connector". The rest of
   the ecosystem is one click away through "See all connectors".
2. **Runport.** Dashed bracket lines drop from each column's centre, merge, and lead into the Runport
   emblem.
3. **Sample run trace.** A dashed line leads to a trace panel: the run root (run id, target, 41.8s)
   and five case rows with status squares, Gantt bars and durations. Invalid output is amber, and
   timeout is red.
4. **Metrics.** A dashed bracket fans out to six cards:
   - Accuracy, highlighted, with its Wilson interval;
   - p95 latency;
   - Cost / 1k cases, tagged ESTIMATED;
   - Invalid output;
   - Agreement κ, marked "not accuracy";
   - Unresolved spend.

All bracket lines are measured from the live layout, so they always meet the elements they connect.

## Motion

The sequence plays once when the panel scrolls into view:

1. The tiles light up, staggered.
2. The top brackets turn cyan and march.
3. The emblem lights with a soft glow.
4. The line drops to the trace.
5. The trace rows fill one at a time.
6. The bottom bracket lights.
7. The metric cards light in order.

The marching dashes run only while the section is on screen. With reduced motion, the finished state
shows immediately with nothing moving. Worst frame: 17ms over 300 frames.

## Responsive behaviour

| Width | Behaviour |
| --- | --- |
| ≥1100px | Three columns; one row of six metrics with the fan-out bracket |
| <1100px | Model providers take a full row and the other two columns sit side by side; metrics go 3 × 2; brackets simplify to one centre line |
| <810px | Columns stack, with 4 tiles per row; trace rows drop the secondary column; metrics go 2 × 3 |

## Size

| Width | v3a | v4 | v5 (now) |
| --- | --- | --- | --- |
| 1440 | about 2,200px | 1,607px | 1,476px |
| 390 | about 3,700px | 2,638px | 1,947px |

## Validation

- `npx tsc`, `npm run build`, `npm run build:landing` and `npm run build:site` pass.
- At 1440, 1280, 1024, 768, 390 and 375: no horizontal overflow, broken images, console errors or
  truncated labels.
- Screenshots: `artifacts/showcase/v5/`.

## Remaining limitations

- Only 16 of the 46 integrations are shown as tiles; the full list is behind "See all connectors".
- The LangGraph and LangChain marks are low-contrast on the dark tiles.
