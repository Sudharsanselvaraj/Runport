"""CLI for KB Audit & Remediation Plugin."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from examples.plugins.kb_audit.audit.models import AuditSummary, IssueSeverity
from examples.plugins.kb_audit.audit.parser import KBParser
from examples.plugins.kb_audit.audit.reporter import KBReporter
from examples.plugins.kb_audit.audit.validator import KBValidator
from runport.cli import compute_sha256

app = typer.Typer(help="KB Audit & Remediation Plugin CLI")
console = Console()


@app.command(name="audit-kb")
def audit_kb(
    file_path: Path = typer.Argument(
        ...,
        help="Path to the knowledge base Markdown file to audit.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output_dir: Path = typer.Option(
        Path("reports"),
        "--output-dir",
        "-o",
        help="Directory to save audit CSV and Markdown reports.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run audit in memory and display summary without writing reports to disk.",
    ),
    report_format: str = typer.Option(
        "both",
        "--format",
        "-f",
        help="Report export format: 'both', 'csv', or 'md'.",
    ),
) -> None:
    """Audit a knowledge base Markdown file for structure, syntax, and content integrity."""
    console.print(Panel(f"[bold cyan]Knowledge Base Audit[/bold cyan]: {file_path.name}", expand=False))

    # 1. Pre-audit SHA-256 verification
    sha_before = compute_sha256(file_path)
    file_size = file_path.stat().st_size

    # 2. Parse source file
    parser = KBParser(file_path)
    q_markers, a_markers, records, headings, orphan_lines = parser.parse()

    # 3. Validate parsed records
    validator = KBValidator(str(file_path), records, headings, orphan_lines)
    issues = validator.validate_all()

    # 4. Post-audit SHA-256 verification (guarantee zero mutation)
    sha_after = compute_sha256(file_path)
    integrity_ok = sha_before == sha_after

    if not integrity_ok:
        console.print("[bold red]CRITICAL INTEGRITY FAILURE: Source file hash changed during audit![/bold red]")
        raise typer.Exit(code=2)

    # 5. Build summary
    error_count = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
    warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)

    summary = AuditSummary(
        source_file=str(file_path.resolve()),
        file_size_bytes=file_size,
        line_count=len(parser.lines),
        sha256_before=sha_before,
        sha256_after=sha_after,
        integrity_verified=integrity_ok,
        raw_question_markers=q_markers,
        raw_answer_markers=a_markers,
        parsed_records_count=len(records),
        error_count=error_count,
        warning_count=warning_count,
        issues=issues,
    )

    # 6. Render terminal tables
    metric_table = Table(title="Audit Metrics Summary", show_header=True, header_style="bold magenta")
    metric_table.add_column("Metric", style="dim")
    metric_table.add_column("Value", justify="right")
    metric_table.add_column("Notes", style="italic")

    metric_table.add_row("Source SHA-256", f"{sha_before[:16]}...", "Pre- and post-audit match verified")
    metric_table.add_row("Total Lines", f"{len(parser.lines):,}", "Original line structure preserved")
    metric_table.add_row("Raw Question Markers", f"{q_markers:,}", "Regex hits across document")
    metric_table.add_row("Raw Answer Markers", f"{a_markers:,}", "Regex hits across document")
    metric_table.add_row("Parsed Q&A Records", f"{len(records):,}", "Structural entities extracted")
    metric_table.add_row(
        "Deterministic Errors",
        f"[bold red]{error_count}[/bold red]" if error_count else "[green]0[/green]",
        "Missing answers, empty fields, malformed syntax",
    )
    metric_table.add_row(
        "Heuristic Warnings",
        f"[bold yellow]{warning_count}[/bold yellow]" if warning_count else "[green]0[/green]",
        "Duplicates, conflicting fees, mismatches, dates",
    )
    console.print(metric_table)

    cat_table = Table(title="Issues Breakdown by Category", show_header=True, header_style="bold blue")
    cat_table.add_column("Category", style="cyan")
    cat_table.add_column("Errors", justify="right", style="red")
    cat_table.add_column("Warnings", justify="right", style="yellow")
    cat_table.add_column("Total", justify="right", style="bold")

    categories = sorted(list(set(i.category.value for i in issues)))
    for cat in categories:
        c_err = sum(1 for i in issues if i.category.value == cat and i.severity == IssueSeverity.ERROR)
        c_warn = sum(1 for i in issues if i.category.value == cat and i.severity == IssueSeverity.WARNING)
        cat_table.add_row(cat, str(c_err), str(c_warn), str(c_err + c_warn))
    console.print(cat_table)

    # 7. Write reports if not dry-run
    if dry_run:
        console.print("[yellow]Dry-run mode enabled: No report files written to disk.[/yellow]")
    else:
        timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = file_path.stem.replace(" ", "_").lower()
        reporter = KBReporter(summary, issues, output_dir)

        if report_format in ("both", "csv"):
            csv_file = reporter.export_csv(f"audit_issues_{safe_name}_{timestamp_slug}.csv")
            console.print(f"[green]✓ CSV issue log saved:[/green] {csv_file}")

        if report_format in ("both", "md"):
            md_file = reporter.export_markdown(f"audit_summary_{safe_name}_{timestamp_slug}.md")
            console.print(f"[green]✓ Markdown summary saved:[/green] {md_file}")

    console.print("[dim]Source file integrity verified: zero modifications made to source.[/dim]")


# ---------------------------------------------------------------------------
# Knowledge Base Remediation Subsystem (Step 2)
# ---------------------------------------------------------------------------


@app.command(name="remediate-kb")
def remediate_kb(
    file_path: Path = typer.Argument(
        Path("examples/plugins/kb_audit/tests/fixtures/synthetic_programmes_kb.md"),
        help="Path to the source knowledge base Markdown file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output_path: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Destination path for versioned clean copy (e.g., data/remediated/Programmes_KB_v1.1_clean.md).",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Write remediated clean copy to output destination. Defaults to dry-run.",
    ),
) -> None:
    """Inspect defect findings, evaluate remediation rules, and produce versioned clean copies."""
    from examples.plugins.kb_audit.remediation.engine import RemediationEngine
    from examples.plugins.kb_audit.remediation.models import RemediationStatus

    console.print(Panel(f"[bold cyan]Knowledge Base Remediation Engine[/bold cyan]: {file_path.name}", expand=False))
    console.print("[yellow]SAFETY INVARIANT: Original knowledge-base source files remain 100% read-only and immutable.[/yellow]\n")

    engine = RemediationEngine(file_path)
    dry_run = not apply

    target_out = output_path or Path("data/remediated") / f"{file_path.stem}_v1.1_clean.md"
    report, _ = engine.execute_remediation(output_path=target_out if apply else None, dry_run=dry_run)

    # 1. Findings Overview Table
    table = Table(title="Remediation Findings & Action Classification", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="bold cyan", width=9)
    table.add_column("Programme", style="white", width=26)
    table.add_column("Classification", style="dim", width=22)
    table.add_column("Status", justify="center", width=24)
    table.add_column("Action / Resolution", style="italic")

    status_styles = {
        RemediationStatus.APPROVED_FOR_RELEASE: "[bold green]APPROVED_FOR_RELEASE[/bold green]",
        RemediationStatus.APPLIED: "[bold green]APPLIED (CLEAN COPY)[/bold green]",
        RemediationStatus.OFFICIAL_VERIFICATION_PENDING: "[bold yellow]OFFICIAL_VERIF_PENDING[/bold yellow]",
        RemediationStatus.INVESTIGATION_PENDING: "[bold cyan]INVESTIGATION_PENDING[/bold cyan]",
        RemediationStatus.KB_OWNER_ESCALATED: "[bold magenta]KB_OWNER_ESCALATED[/bold magenta]",
    }

    for f in report.findings:
        st_label = status_styles.get(f.status, str(f.status.value))
        table.add_row(f.finding_id, f.programme_name[:26], f.classification.value, st_label, f.resolution_notes or f.issue_title)

    console.print(table)

    # 2. Summary Card
    mode_text = "[bold green]LIVE VERSIONED WRITE[/bold green]" if apply else "[bold yellow]DRY-RUN (In-Memory Evaluation)[/bold yellow]"
    summary_card = (
        f"Execution Mode:       {mode_text}\n"
        f"Source SHA-256:       {report.sha256_original[:16]}... (Verified 100% Immutable)\n"
        f"Total Findings:       {report.total_findings}\n"
        f"Approved for Clean:   {report.approved_count} (Confirmed Content Defects)\n"
        f"Official Verif Req:   {report.pending_official_verification_count} (Contradictory Fees / Intakes — Zero Guessing)\n"
        f"KB Owner Escalations: {report.escalated_kb_owner_count} (Curriculum / Language Standards)\n"
    )
    if apply and output_path:
        summary_card += f"Output Destination:   {target_out}\nRemediated SHA-256:   {report.sha256_remediated[:16]}...\n"
    elif dry_run:
        summary_card += f"\n[dim]Run with '--apply --output {target_out}' to generate versioned clean copy.[/dim]"

    console.print(Panel(summary_card, title="[bold]Remediation Execution Summary[/bold]", border_style="cyan"))
