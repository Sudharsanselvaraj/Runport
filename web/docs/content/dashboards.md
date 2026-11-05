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

### Access policy

The API (`/api/*`) has two modes. Static dashboard files are not gated; `/api/health` and the API docs are always open.

**Local development (no `RUNPORT_API_TOKEN`).** Only loopback clients are served (`127.0.0.1`, `::1`), and only when the request's
`Host` header is a loopback name (`localhost`, `127.0.0.1`, `[::1]`) or a name listed in `RUNPORT_ALLOWED_HOSTS`. Any other client
gets `403`, whatever credentials it sends, so remote access fails closed until a token is configured. The `Host` check stops a web
page you visit from reaching the API through DNS rebinding.

**Network deployment (`RUNPORT_API_TOKEN` set).** Every API request, local or remote, must send exactly that token as
`Authorization: Bearer <token>` or `X-Runport-Token: <token>` (compared in constant time); otherwise `401`. `runport web` refuses
to bind a non-loopback host without a token. The bundled dashboard does not send a token yet, so in this mode use the CLI, the
SDK or the API directly, or put the dashboard behind a reverse proxy that adds the header.

> [!WARNING]
> Approving a plan in the dashboard authorizes live spend. Anyone who can reach the API can approve, so never give the token, or
> loopback access through a proxy, to an agent. Agents should use `runport mcp serve`, which cannot approve anything.

## Terminal UI

```bash
uv run runport ui
```

A full-screen Rich interface with spend, remaining ceilings, model readiness and error rates. `runport ui --web` starts the web dashboard instead.

## Interactive launcher

`uv run runport` with no command opens a menu that reaches the same workflows.
