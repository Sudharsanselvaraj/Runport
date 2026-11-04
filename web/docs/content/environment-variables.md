---
title: Environment variables
description: Every environment variable Runport reads, and how .env files are handled.
---

| Variable | Used by | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | OpenRouter provider, `api-preflight` | Key for live OpenRouter runs |
| `RUNPORT_API_TOKEN` | `runport web`, the API | Required to bind the web server to a non-loopback host; API requests must then send it |
| `DOTENV_PATH` | Configuration | Load this `.env` file instead of the default |
| `RUNPORT_SKIP_DOTENV` | Configuration | Set to `1` to skip loading `.env` (used by the offline tests) |
| `RUNPORT_LOGO_STYLE` | Terminal UI | Choose the terminal logo style |
| `NO_COLOR` | Terminal output | Disable colour |

Keys for other providers (OpenAI-compatible servers, Dify, Flowise and so on) are passed to connectors in Python; the variable names are yours to choose.

## .env files

Runport loads a `.env` file from the project root, or from the current directory if there is none at the root. It does not search parent directories.

- Variables already exported in your shell win over `.env`.
- On POSIX systems the file's permissions are set to `0600`.
- `runport api-preflight` tells you whether the key came from the shell or from `.env`, without printing it.

> [!WARNING]
> Never commit `.env` files. The repository's `.gitignore` excludes them.
