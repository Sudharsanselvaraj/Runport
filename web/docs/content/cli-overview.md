---
title: CLI overview
description: How the runport command is organized, and the options every command shares.
---

The `runport` command is built with Typer. Run it through `uv run` from a cloned repository, or directly if it is installed into your environment.

```bash
uv run runport --help
```

## Interactive launcher

With no command, `runport` opens an interactive launcher with shortcuts to the main commands:

```bash
uv run runport
```

`runport welcome` shows the welcome screen directly, and `runport -i` launches the interactive terminal UI.

## Global options

| Option | Meaning |
|---|---|
| `-i`, `--interactive` | Launch the interactive terminal UI |
| `--install-completion` | Install shell completion |
| `--show-completion` | Print the completion script |
| `--help` | Show help for any command |

## Command groups

| Area | Commands |
|---|---|
| Workspace | `init` |
| Data | `validate-dataset`, `annotate` |
| Benchmarks | `benchmark`, `benchmark-rag`, `smoke-test`, `compare-runs` |
| Budget | `budget status`, `budget audit`, `budget policy`, `budget reconcile`, `budget raise-pilot-ceiling`, `budget purge-simulated` |
| Models | `models roster`, `models list` |
| Keys | `api-preflight` |
| Traces | `export-traces`, `import-traces` |
| Interfaces | `ui`, `web`, `welcome` |

Every command and option is listed in [Commands](/cli-commands) and [Budget commands](/cli-budget).

## Safe defaults

- Commands that could spend money do nothing without `--live`, and `--live` always asks for a typed confirmation.
- `api-preflight`, `validate-dataset`, `annotate`, `budget status`, `budget audit`, `budget policy` and `export-traces` never send a network request.
- Exports never overwrite existing files.
