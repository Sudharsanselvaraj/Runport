# RAG evaluation: candidate planner models and prices

Source: OpenRouter public endpoints metadata (`https://openrouter.ai/api/v1/models/<slug>/endpoints`), fetched 2026-10-29. The model pages themselves served a generic API guide, so every figure below comes from the endpoints JSON, read by a fetch agent and not re-read by hand. Prices are USD per 1M tokens, listed raw (the JSON also carries a `discount` field that neither page explains). Prices change; re-fetch before a run that matters.

The owner's cost table (50 cases at 700 in / 100 out) reconciles exactly with these prices on all 11 routes checked (Haiku on AWS, Luna OpenAI and Bedrock, Qwen3.5-35B-A3B Alibaba/DeepInfra/Venice, Gemini Vertex and Flex, DeepSeek Wafer mxfp4/Inference.net/CoreWeave).

## What changes in the flow

Only the planner node ("Search AI Planner", currently `openai/gpt-6-luna` through the OpenAI plugin) is replaced. The responder node (`google/gemini-3.5-flash-lite` through OpenRouter) and the clarification guard stay fixed, so differences come from the planner.

| Variant | OpenRouter slug | Standard in / out | Notes from the endpoints data |
|---|---|---|---|
| Baseline: GPT-6 Luna | `openai/gpt-6-luna` | 0.10 / 0.50 (OpenAI) | reasoning, reasoning_effort, structured_outputs on all endpoints; temperature and top_p NOT listed |
| Claude Haiku 5.5 | `anthropic/claude-haiku-5.5` | 0.10 / 0.50 | structured_outputs on 6 of 10 endpoints; NOT on Claude Platform on AWS or Bedrock; temperature and top_p NOT listed |
| Gemini 3.5 Flash Lite | `google/gemini-3.5-flash-lite` | 0.30 / 2.50 (Google standard) | structured_outputs and reasoning on all; temperature and top_p only on AI Studio |
| DeepSeek V4.1 Flash | `deepseek/deepseek-v4.1-flash` | 0.30 / 1.20 (most providers); 41 endpoints from 0.0099 to 0.60 in | structured_outputs on 35 of 41 (not Alibaba, GMICloud, Novita, Phala, SiliconFlow, StreamLake) |
| Qwen3.5-35B-A3B | `qwen/qwen3.5-35b-a3b` | 0.15 / 1.00 (Parasail, Venice); range 0.065-0.24 in, 0.75-1.80 out | structured_outputs and reasoning on all 7; `reasoning_effort` NOT listed |
| Qwen 3.5 Flash | `qwen/qwen3.5-flash-02-23` | 0.065 / 0.26 (Alibaba, the only provider) | structured_outputs and reasoning listed; `reasoning_effort` NOT listed; 1M context, 65,536 max output; reconciles with the owner's $0.00358 for 50 cases at 700 in / 100 out. The slug `qwen/qwen3.5-flash` returns 404; this dated id was found in OpenRouter's public model list on 2026-10-30. |

## Routes named in the owner's table

| Model | Route | In / out | structured_outputs |
|---|---|---|---|
| Claude Haiku 5.5 | Claude Platform on AWS (`claude-on-aws`) | 0.10 / 0.50 | **no** |
| | Google Vertex (`google-vertex/global`) | 0.10 / 0.50 | yes |
| | Azure (`azure/global`) | 0.10 / 0.50 | yes |
| GPT-6 Luna | OpenAI (`openai`) | 0.10 / 0.50 | yes |
| | Azure (`azure`) | 0.10 / 0.50 | yes |
| | Amazon Bedrock (`amazon-bedrock/us-east-1`) | 0.11 / 0.55 | yes |
| Qwen3.5-35B-A3B | Alibaba (`alibaba`) | 0.1625 / 1.30 | yes |
| | DeepInfra (`deepinfra/fp8`) | 0.14 / 1.00 | yes |
| | Venice (`venice`) | 0.15 / 1.00 | yes |
| Gemini 3.5 Flash Lite | Google Vertex (`google-vertex/global`) | 0.30 / 2.50 | yes |
| | Google AI Studio (`google-ai-studio`) | 0.30 / 2.50 | yes |
| | AI Studio Flex (`google-ai-studio/flex`) | 0.15 / 1.25 | yes |
| DeepSeek V4.1 Flash | Wafer (`wafer/mxfp4`) | 0.19 / 0.65 | yes |
| | Inference.net (`inference-net/fp8`) | 0.103 / 0.60 | yes |
| | CoreWeave (`coreweave/fp8`) | 0.13 / 0.65 | yes |

Caveats that matter for the run:

- The planner uses strict structured output. Haiku's first-listed route (Claude Platform on AWS) does not list it.
- The planner sends `reasoning_effort: low` and `max_tokens: 4096`. Qwen3.5-35B-A3B does not list `reasoning_effort`; Luna and Haiku list no `temperature`/`top_p`.
- Dify's OpenRouter plugin may not let you pin a provider route, so the run may compare models, not routes. This is unverified.

## Cost estimate for the planned run (ESTIMATE, not a quote)

Assumptions, stated so they can be challenged: planner system prompt about 6,600 tokens plus about 1,900 tokens of user template and retrieved text per call, 3 planner calls per case at most, about 350 output tokens per call; responder about 6,700 input and 250 output tokens, fixed at Gemini 3.5 Flash Lite 0.30 / 2.50. Real token counts come from the pilot.

| Planner | Per case | 50 cases |
|---|---|---|
| GPT-6 Luna (0.10 / 0.50) | about $0.0057 | about $0.29 |
| Claude Haiku 5.5 (0.10 / 0.50) | about $0.0057 | about $0.29 |
| Qwen3.5-35B-A3B (0.15 / 1.00) | about $0.0075 | about $0.38 |
| DeepSeek V4.1 Flash (0.30 / 1.20) | about $0.0115 | about $0.58 |
| Gemini 3.5 Flash Lite (0.30 / 2.50) | about $0.0129 | about $0.65 |

Each figure includes about $0.0026 per case for the fixed responder. Baseline plus five candidates, one pass over 50 cases: roughly $2.45 (the five candidates alone are about $2.17). Reasoning tokens or retries would add to this. Gemini at about $0.0129 per case is closer to the old $0.02 per-case ceiling than the others, so a reasoning-heavy planner could trip it; the pilot's measured tokens decide.
