---
title: Plugins
description: Ship custom targets and scorers as Python packages that Runport discovers through entry points.
---

Runport discovers extensions through standard Python packaging entry points, so a plugin is an ordinary package you install next to Runport.

| Entry-point group | Loaded by | Provides |
|---|---|---|
| `runport.targets` | `load_plugin_targets()` | Target classes or factories |
| `runport.scorers` | `load_plugin_scorers()` | Scorer classes |
| `runport.plugins` | `discover_plugins()` | General extensions |

All three live in `runport.core.plugins`.

## Register a plugin

In your package's `pyproject.toml`:

```toml
[project.entry-points."runport.targets"]
my_target = "my_package.targets:MyTarget"

[project.entry-points."runport.scorers"]
my_scorer = "my_package.scorers:MyScorer"
```

After `pip install` (or `uv add`), Runport can load them:

```python
from runport.core.plugins import load_plugin_targets, load_plugin_scorers

targets = load_plugin_targets()   # {"my_target": MyTarget}
scorers = load_plugin_scorers()   # {"my_scorer": MyScorer}
```

A plugin that fails to import is skipped with a warning; it does not stop discovery of the others.

## Writing the classes

- Targets subclass `runport.targets.base.Target` and implement `execute()`; see [Creating benchmarks](/creating-benchmarks#1-choose-or-write-a-target).
- Scorers subclass `runport.scorers.base.BaseScorer` and implement `score()`; see [Scorers](/scorers#the-contract).

## Reference implementations

`examples/plugins/` contains two decoupled plugins with their own tests: `kb_audit` (knowledge-base audit and remediation) and `jev_decisions_api` (a decisions-API adapter). Run their tests with:

```bash
uv run pytest examples/plugins
```
