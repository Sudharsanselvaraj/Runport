---
title: Contribution guidelines
description: How to propose a change, and the rules every contribution follows.
---

Contributions are welcome: bug fixes, connectors, scorers and documentation.

## Process

1. Fork the repository and create a feature branch.
2. Make the change with tests.
3. Run the full test suite, the linters and a secret scan (`gitleaks detect`).
4. Open a pull request against `main` with a clear summary.

## Rules

- **Keep the invariants.** Never weaken the [invariants](/invariants): no fabricated telemetry, the fixed cost vocabulary, the guard order, fail-closed spend, plan fingerprints, immutable sources, secret scrubbing, agreement ≠ accuracy, no tuning on held-out data, no simulation in core.
- **One logical change per commit**, with a concise imperative message (for example `fix(budget): reject negative spend amounts`).
- **No secrets or runtime artifacts** in commits: `.env*`, databases, `reports/`, private datasets.
- **No unrelated refactoring** in the same change.

## Security

Report vulnerabilities privately as described in `SECURITY.md` in the repository, not in a public issue.

## Licence

Runport is licensed under Apache 2.0. Contributions are accepted under the same licence.
