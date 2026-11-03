"""Benchmark report generation with cryptographic run manifest and auto-generated statistical caveats."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from runport.scorers.stats import wilson


@dataclass
class RunManifest:
    """Cryptographic run manifest establishing provenance and verification."""

    run_id: str
    plan_id: str
    plan_fingerprint: str
    models: List[str]
    dataset_path: str
    dataset_hash: str
    total_cases: int
    spend_by_basis: Dict[str, str] = field(default_factory=dict)
    generated_at: str = ""

    def __post_init__(self):
        if not self.generated_at:
            self.generated_at = datetime.now(timezone.utc).isoformat()


def generate_caveats(
    total_cases: int,
    unverified_cases: int = 0,
    unresolved_spend_count: int = 0,
    is_synthetic: bool = False,
    accuracy: Optional[float] = None,
) -> List[str]:
    """Generate objective, mathematically grounded caveats from evaluation parameters."""
    caveats: List[str] = []

    # 1. Sample size statistical caveats
    if total_cases < 30:
        if accuracy is not None and 0.0 <= accuracy <= 1.0:
            k = int(round(accuracy * total_cases))
            lo, hi = wilson(k, total_cases)
            caveats.append(
                f"Small sample size (N={total_cases}): 95% Wilson confidence interval spans "
                f"[{lo * 100:.1f}%, {hi * 100:.1f}%]. Do not treat point accuracy as a statistically stable threshold."
            )
        else:
            caveats.append(f"Small sample size (N={total_cases} < 30): Underpowered for high-confidence statistical significance.")

    # 2. Ground-truth approval caveats (Invariant 8)
    if unverified_cases > 0:
        caveats.append(
            f"Ground Truth Pending: {unverified_cases} cases have not been verified by human annotators. "
            "Supervised metrics (accuracy, calibration) require human ground truth approval and cannot be guaranteed."
        )

    # 3. Spend completeness caveats (Invariant 2 & 4)
    if unresolved_spend_count > 0:
        caveats.append(
            f"Unresolved Cost: {unresolved_spend_count} requests were billed with unknown cost and remain UNRESOLVED. "
            "Total reported spend is an underestimate until reconciled via 'runport budget reconcile'."
        )

    # 4. Parity with production caveats
    if is_synthetic:
        caveats.append(
            "Synthetic Fixture Data: Parity with production distribution has not been established. "
            "Live system behavior may diverge under real query distributions."
        )

    return caveats


class ReportGenerator:
    """Generates Markdown and JSON benchmark evaluation reports."""

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path("reports")

    def build_markdown_report(
        self,
        manifest: RunManifest,
        summary_metrics: Dict[str, Any],
        case_rows: Optional[List[Dict[str, Any]]] = None,
        unverified_cases: int = 0,
        unresolved_spend_count: int = 0,
        is_synthetic: bool = False,
    ) -> str:
        acc = summary_metrics.get("mean_accuracy")
        caveats = generate_caveats(
            total_cases=manifest.total_cases,
            unverified_cases=unverified_cases,
            unresolved_spend_count=unresolved_spend_count,
            is_synthetic=is_synthetic,
            accuracy=acc,
        )

        lines: List[str] = [
            f"# Runport Benchmark Evaluation Report — {manifest.run_id}",
            "",
            "## Cryptographic Run Manifest",
            "",
            f"- **Run ID:** `{manifest.run_id}`",
            f"- **Plan ID:** `{manifest.plan_id}`",
            f"- **Plan Fingerprint:** `{manifest.plan_fingerprint}`",
            f"- **Evaluated Models:** {', '.join(f'`{m}`' for m in manifest.models)}",
            f"- **Dataset Path:** `{manifest.dataset_path}`",
            f"- **Dataset SHA-256:** `{manifest.dataset_hash}`",
            f"- **Total Cases:** `{manifest.total_cases}`",
            f"- **Generated At (UTC):** `{manifest.generated_at}`",
            "",
            "### Spend Accounting by Basis",
            "",
        ]

        if manifest.spend_by_basis:
            for basis, amt in sorted(manifest.spend_by_basis.items()):
                lines.append(f"- **{basis}:** `${amt}`")
        else:
            lines.append("- No spend recorded.")

        lines.extend(
            [
                "",
                "## Summary Metrics",
                "",
                "| Metric | Value |",
                "|---|---|",
            ]
        )

        for k, v in summary_metrics.items():
            fmt_v = f"{v:.4f}" if isinstance(v, float) else str(v)
            lines.append(f"| {k} | {fmt_v} |")

        if caveats:
            lines.extend(
                [
                    "",
                    "## Statistical & Methodological Caveats",
                    "",
                ]
            )
            for c in caveats:
                lines.append(f"> [!WARNING]\n> {c}\n")

        if case_rows:
            lines.extend(
                [
                    "",
                    "## Per-Case Results Breakdown",
                    "",
                    "| Case ID | Status | Output Snippet | Latency (ms) |",
                    "|---|---|---|---|",
                ]
            )
            for r in case_rows[:25]:
                cid = r.get("case_id", "—")
                st = r.get("status", "—")
                snip = (str(r.get("output", ""))[:40] + "...").replace("\n", " ")
                lat = r.get("latency_ms", "—")
                lines.append(f"| {cid} | {st} | {snip} | {lat} |")

        return "\n".join(lines) + "\n"

    def export_report(
        self,
        manifest: RunManifest,
        summary_metrics: Dict[str, Any],
        case_rows: Optional[List[Dict[str, Any]]] = None,
        unverified_cases: int = 0,
        unresolved_spend_count: int = 0,
        is_synthetic: bool = False,
    ) -> Path:
        """Export Markdown and JSON report files to destination directory."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        md_text = self.build_markdown_report(
            manifest=manifest,
            summary_metrics=summary_metrics,
            case_rows=case_rows,
            unverified_cases=unverified_cases,
            unresolved_spend_count=unresolved_spend_count,
            is_synthetic=is_synthetic,
        )

        md_path = self.output_dir / f"report_{manifest.run_id}.md"
        md_path.write_text(md_text, encoding="utf-8")

        json_data = {
            "manifest": manifest.__dict__,
            "summary_metrics": summary_metrics,
            "caveats": generate_caveats(
                total_cases=manifest.total_cases,
                unverified_cases=unverified_cases,
                unresolved_spend_count=unresolved_spend_count,
                is_synthetic=is_synthetic,
                accuracy=summary_metrics.get("mean_accuracy"),
            ),
        }
        json_path = self.output_dir / f"report_{manifest.run_id}.json"
        json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")

        return md_path
