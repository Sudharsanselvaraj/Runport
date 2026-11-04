---
title: Installation
description: Install Runport from source with uv or pip and verify the CLI.
---

## Requirements

- Python **3.11, 3.12 or 3.13**
- [`uv`](https://docs.astral.sh/uv/) (recommended) or `pip`
- Git

Runport has no hosted service and needs no account.

## Install with uv

Clone the repository and install the dependencies. The `dev` extra adds the test tools; the `report` extra adds report dependencies.

```bash
git clone https://github.com/Sudharsanselvaraj/runport.git
cd runport
uv sync --extra dev --extra report
```

| Extra | Adds | Needed for |
|---|---|---|
| `report` | numpy, pandas, scipy, matplotlib, reportlab and others | `runport.scorers` statistics and reports |
| `dev` | pytest, httpx, numpy, scipy, pandas, ruff, mypy | Running the test suite |
| `monitor` | psutil | Host resource monitoring |

> [!NOTE]
> `runport.scorers` imports numpy and pandas for its statistics helpers. Install the `report` (or `dev`) extra before using scorers from Python.

Run the CLI through `uv run`:

```bash
uv run runport --help
```

## Install with pip

From the cloned repository, in a virtual environment:

```bash
pip install -e .
runport --help
```

## Verify the installation

The interactive launcher with no arguments opens a menu of the main commands:

```bash
uv run runport
```

Then check your environment without sending any request:

```bash
uv run runport api-preflight
```

`api-preflight` reports whether `OPENROUTER_API_KEY` is available and where it came from (shell or `.env`), without printing the key and without opening a network connection. A missing key is fine for offline work.

## Optional: the web dashboard frontend

The Python package serves a prebuilt dashboard. To work on the frontend itself you also need Node.js; see [Development setup](/development-setup).

## Next

Continue with the [Quickstart](/quickstart).
