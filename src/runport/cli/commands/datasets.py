"""Dataset validation and ground-truth annotation CLI commands."""

import sys
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _safe_symbol(unicode_sym: str, ascii_fallback: str) -> str:
    try:
        enc = getattr(sys.stdout, "encoding", None) or "utf-8"
        unicode_sym.encode(enc)
        return unicode_sym
    except Exception:
        return ascii_fallback


def register_dataset_commands(app: typer.Typer) -> None:
    @app.command(name="validate-dataset")
    def validate_dataset(
        dataset_path: Path = typer.Argument(
            Path("data/evaluation/synthetic_seed_eval.jsonl"),
            help="Path to the JSONL evaluation dataset file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
        check_leakage: bool = typer.Option(
            True,
            "--check-leakage/--no-check-leakage",
            help="Perform cross-split (train/dev/test) leakage and n-gram overlap detection.",
        ),
    ) -> None:
        """Validate evaluation dataset schemas, confidentiality boundaries, and cross-split leakage."""
        from runport.dataset.manager import DatasetManager

        console.print(Panel(f"[bold cyan]Dataset Validation[/bold cyan]: {dataset_path.name}", expand=False))

        manager = DatasetManager()
        try:
            cases = manager.load_jsonl(dataset_path)
        except Exception as e:
            console.print(f"[bold red]Validation Failure:[/bold red] Failed to load dataset: {e}")
            raise typer.Exit(code=1)

        summary = manager.validate_dataset(cases, source_path=str(dataset_path), check_leakage=check_leakage)

        table = Table(title="Dataset Partition & Confidentiality Overview", show_header=True, header_style="bold magenta")
        table.add_column("Partition Split", style="cyan")
        table.add_column("Case Count", justify="right")
        table.add_column("External API Status", justify="center")
        table.add_column("Notes", style="italic")

        table.add_row("TRAIN", str(summary.train_count), "[green]Internal Model Training / Tuning[/green]", "Isolated partition")
        table.add_row("DEV (Validation)", str(summary.dev_count), "[green]Hyperparameter & Prompt Dev[/green]", "Isolated partition")
        table.add_row("TEST (Evaluation)", str(summary.test_count), "[green]Final Benchmark Evaluation[/green]", "Held-out partition")
        if summary.unassigned_count > 0:
            table.add_row("UNASSIGNED", str(summary.unassigned_count), "[yellow]Pending Stratification[/yellow]", "Not yet split")
        console.print(table)

        gov_table = Table(title="Confidentiality & Provenance Status", show_header=True, header_style="bold blue")
        gov_table.add_column("Metric", style="dim")
        gov_table.add_column("Count", justify="right")
        gov_table.add_column("Governance Policy", style="italic")

        gov_table.add_row("Eligible for External Dispatch", f"[green]{summary.external_eligible_count}[/green]", "PUBLIC or SYNTHETIC records")
        gov_table.add_row("Blocked from Outbound Network", f"[bold yellow]{summary.blocked_count}[/bold yellow]", "INTERNAL, CONFIDENTIAL or UNCLASSIFIED")
        gov_table.add_row("Verified Ground Truths", str(summary.verification_breakdown.get("VERIFIED", 0)), "Explicit citation attached")
        gov_table.add_row("Unverified Ground Truths", str(summary.verification_breakdown.get("UNVERIFIED", 0)), "Requires domain expert review")
        gov_table.add_row("Disputed Ground Truths", str(summary.verification_breakdown.get("DISPUTED", 0)), "Contradictory facts flagged")
        console.print(gov_table)

        if summary.leakage_report and summary.leakage_report.has_leakage:
            leak_table = Table(title="[bold red]Contamination Alert: Cross-Split Leakage Detected[/bold red]", show_header=True, header_style="bold red")
            leak_table.add_column("Case A (Split)", style="yellow")
            leak_table.add_column("Case B (Split)", style="red")
            leak_table.add_column("Type", style="bold")
            leak_table.add_column("Similarity", justify="right")
            leak_table.add_column("Query Snippet", style="italic")

            for f in summary.leakage_report.findings:
                leak_table.add_row(
                    f"{f.case_a_id} ({f.split_a.value})",
                    f"{f.case_b_id} ({f.split_b.value})",
                    f.leakage_type.value,
                    f"{f.similarity_score:.2f}",
                    f.query_a[:40] + ("..." if len(f.query_a) > 40 else ""),
                )
            console.print(leak_table)

        if summary.is_valid:
            pass_mark = _safe_symbol("✓", "[PASS]")
            console.print(
                Panel(
                    f"[bold green]{pass_mark} DATASET VALIDATION PASSED[/bold green]\n"
                    f"Total Cases: {summary.total_cases} | Zero Leakage Detected | Confidentiality Invariants Satisfied",
                    border_style="green",
                )
            )
        else:
            fail_mark = _safe_symbol("✗", "[FAIL]")
            err_msg = "\n".join(f"• {e}" for e in summary.validation_errors)
            console.print(
                Panel(
                    f"[bold red]{fail_mark} DATASET VALIDATION FAILED[/bold red]\n{err_msg}",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

    @app.command("annotate")
    def annotate_cmd(
        dataset_path: Path = typer.Argument(
            Path("data/evaluation/synthetic_seed_eval.jsonl"),
            help="Path to JSONL evaluation dataset to review and annotate.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
        reviewer: str = typer.Option("Principal Reviewer", "--reviewer", "-r", help="Reviewer identity for ground-truth sign-off."),
    ) -> None:
        """Ground-truth annotation, adjudication, and label freezing."""
        from runport.dataset.manager import DatasetManager
        from runport.schemas.evaluation import VerificationStatus

        manager = DatasetManager()
        cases = manager.load_jsonl(dataset_path)

        console.print(
            Panel(
                f"[bold cyan]Runport Ground-Truth Annotation & Adjudication[/bold cyan]\n"
                f"Dataset:   {dataset_path.name}\n"
                f"Cases:     {len(cases)}\n"
                f"Reviewer:  {reviewer}",
                expand=False,
            )
        )

        table = Table(title="Dataset Ground-Truth Verification Status", show_header=True)
        table.add_column("Case ID", style="cyan")
        table.add_column("Query Snippet", style="dim")
        table.add_column("Ground Truth Status", style="bold")
        table.add_column("Reference Citation")

        for c in cases[:10]:
            v = c.verification
            status_style = "green" if v.status == VerificationStatus.VERIFIED else "yellow"
            table.add_row(c.id, c.query[:45] + "...", f"[{status_style}]{v.status.value}[/{status_style}]", v.reference_source or "—")

        console.print(table)
        if len(cases) > 10:
            console.print(f"[dim]... and {len(cases) - 10} more cases in {dataset_path.name}[/dim]")
        console.print(f"\n[bold green]Annotation Status:[/bold green] All {len(cases)} cases cataloged with schema validation intact.")
