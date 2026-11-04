---
title: Web and terminal dashboards
description: The local web dashboard and the Rich terminal UI.
---

Both dashboards read the same local database as the CLI. Neither sends data anywhere.

## Web dashboard

```bash
uv run runport web
```

Open `http://127.0.0.1:8000` in a browser. The dashboard is a React app served by a FastAPI backend, with these sections: Setup, Models, Targets, Datasets, Plan, Live Run, Results, Compare, Reports and Budget.

| Option | Default |
|---|---|
| `--host` | `127.0.0.1` |
| `--port` | `8000` |
| `--reload` / `--no-reload` | `--no-reload` |

### Binding to another host

Binding to anything other than a loopback address (for example `0.0.0.0`) is refused unless `RUNPORT_API_TOKEN` is set. With a token set, API requests must send it as `Authorization: Bearer ...` or `X-Runport-Token`; the health and API-docs endpoints stay open.

> [!WARNING]
> The dashboard can start live runs. Only expose it on a network you trust, and always with `RUNPORT_API_TOKEN`.

## Terminal UI

```bash
uv run runport ui
```

A full-screen Rich interface with spend, remaining ceilings, model readiness and error rates. `runport ui --web` starts the web dashboard instead.

## Interactive launcher

`uv run runport` with no command opens a menu that reaches the same workflows.
