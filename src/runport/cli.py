"""CLI entry point for runport."""

import hashlib
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from runport.core.budget import BudgetService
from runport.models.catalog import get_portfolio
import sys

app = typer.Typer(
    name="runport",
    help="Runport: Universal open-source LLM, prompt, and workflow benchmarking platform.",
    no_args_is_help=False,
)
budget_app = typer.Typer(
    name="budget",
    help="Budget ledger, ceilings, and spend tracking.",
    no_args_is_help=True,
)
models_app = typer.Typer(
    name="models",
    help="Model portfolio catalog and validation.",
    no_args_is_help=True,
)

app.add_typer(budget_app, name="budget")
app.add_typer(models_app, name="models")

console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Launch interactive terminal UI.",
    ),
) -> None:
    """Runport LLM and Workflow Benchmarking Platform."""
    if ctx.invoked_subcommand is None:
        if interactive:
            from runport.tui.app import run_tui
            run_tui()
        elif sys.stdin.isatty():
            run_launcher_loop()
        else:
            console.print(ctx.get_help())


def _run_command(args: List[str]) -> None:
    """Run a CLI command in-process exactly as if typed, so every option keeps its real default (calling a command function directly
    would hand it unresolved Typer option objects)."""
    try:
        app(args=args, standalone_mode=False)
    except (SystemExit, typer.Exit):
        pass
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
    except Exception as e:  # keep the launcher alive; show what failed instead of a traceback
        console.print(f"[bold red]Command failed:[/bold red] {type(e).__name__}: {e}")


def handle_welcome_action(choice: int) -> None:
    """Dispatches one launcher choice to a real workflow. Nothing here simulates anything or sends data."""
    if choice == 1:
        from runport.tui.app import run_tui
        run_tui()
    elif choice == 2:
        console.print("\n[bold #c084fc]Knowledge Base Audit Plugin:[/]")
        console.print("  Located under: [dim]examples/plugins/kb_audit/[/dim]")
        console.print("  See [cyan]examples/plugins/kb_audit/README.md[/cyan] for usage instructions.")
    elif choice == 3:
        _run_command(["validate-dataset", "data/evaluation/verified_rag_benchmark.jsonl"])
    elif choice == 4:
        _run_command(["models", "roster"])
        console.print("\n[dim]Next: api-preflight (menu 5), then the RAG benchmark (menu 6).[/dim]")
    elif choice == 5:
        _run_command(["api-preflight"])
    elif choice == 6:
        _run_command(["benchmark-rag"])
    elif choice == 7:
        _run_command(["budget", "status"])
    elif choice == 8:
        from runport.core.config import settings
        console.print("\n[bold #c084fc]Runport Environment & Workspace Configuration:[/]")
        console.print(f"  App Name:          [green]{settings.app_name}[/]")
        console.print(f"  Data Directory:    [green]{settings.data_dir}[/]")
        console.print(f"  Reports Directory: [green]{settings.reports_dir}[/]")
        console.print(f"  Database Path:     [green]{settings.db_path}[/]")
    elif choice == 9:
        console.print("[dim]Exiting Runport. Goodbye.[/]\n")


def run_launcher_loop() -> None:
    """Show the launcher, run the chosen workflow, then come back to the menu. Only 'Exit' (9), q or Esc leaves."""
    from runport.tui.welcome import MENU_ITEMS, show_welcome_screen

    exit_choice = len(MENU_ITEMS)
    while True:
        choice = show_welcome_screen()
        handle_welcome_action(choice)
        if choice == exit_choice or choice == 0:
            break
        if choice != 1:  # the dashboard is full-screen and returns straight to the menu; command output needs a pause to be read
            try:
                console.input("\n[dim]Press Enter to return to the menu...[/dim]")
            except (EOFError, KeyboardInterrupt):
                break


def _require_live_confirmation(models: List[str], dataset_name: str):
    """Fail closed: a live run needs interactive typed confirmation, or the command exits before any request."""
    from runport.core.live_guard import confirm_live_run
    from runport.providers.base import LiveNotAuthorizedError

    summary = [
        f"Live run requested. Models: {', '.join(models)}. Dataset: {dataset_name}.",
        "Local spend ceilings still apply (preflight and per-case circuit breaker).",
    ]
    try:
        return confirm_live_run(models, summary, echo=lambda line: console.print(line, markup=False, highlight=False))
    except LiveNotAuthorizedError as e:
        console.print(f"[bold red]Live run refused:[/bold red] {e}")
        raise typer.Exit(code=1)




@models_app.command("roster")
def models_roster() -> None:
    """Show registered model portfolio candidates and their attributes."""
    from runport.models.catalog import get_portfolio

    models = get_portfolio()
    table = Table(title=f"Registered Model Portfolio ({len(models)} models)", show_header=True, header_style="bold magenta")
    table.add_column("Model ID")
    table.add_column("Display Name")
    table.add_column("Provider")
    table.add_column("Deployment Mode")
    table.add_column("Input $/1M")
    table.add_column("Output $/1M")
    table.add_column("Status")
    for m in models:
        table.add_row(
            m.model_id,
            m.display_name,
            m.provider,
            m.deployment_mode,
            f"${m.input_price_per_1m_usd:.4f}",
            f"${m.output_price_per_1m_usd:.4f}",
            m.verification_status,
        )
    console.print(table)


@app.command("export-traces")
def export_traces_cmd(
    fmt: str = typer.Option("zip", "--format", "-f", help="jsonl, csv or zip (zip = per-model files, comparison file and manifest)."),
    model: List[str] = typer.Option([], "--model", "-m", help="Limit to a model key (repeatable)."),
    run: List[str] = typer.Option([], "--run", "-r", help="Limit to a run id (repeatable)."),
    task: Optional[str] = typer.Option(None, "--task", "-t", help="Task filter (e.g. classification, benchmark, rag)."),
    status: List[str] = typer.Option([], "--status", "-s", help="OK, INVALID_OUTPUT or ERROR (repeatable)."),
    out_dir: Optional[Path] = typer.Option(None, "--out-dir", help="Destination folder (default: reports/exports)."),
) -> None:
    """Export stored trace records (redacted, local only). Reads the prediction store and event log; sends nothing; never overwrites."""
    from runport.core.config import settings
    from runport.models.registry import roster_status
    from runport.observability.export import ExportError, ExportSelection, build_trace_rows, export_traces
    from runport.observability.monitor import LiveMonitor

    fmt_val = getattr(fmt, "default", fmt) if hasattr(fmt, "default") else fmt
    task_val = getattr(task, "default", task) if hasattr(task, "default") else task
    if task_val is not None and str(task_val).upper() not in ("INTENT", "LEAD", "CLASSIFICATION", "BINARY", "RAG"):
        console.print(f"[bold red]Invalid --task: {task_val}[/bold red]")
        raise typer.Exit(code=1)
    mon = LiveMonitor()
    mon.poll()
    preds, events, labels, frozen = mon.trace_inputs()
    sel = ExportSelection(
        models=tuple(model) or None,
        runs=tuple(run) or None,
        task=str(task_val) if task_val else None,
        statuses=tuple(status) or None,
    )
    ts = build_trace_rows(preds, events, labels, frozen, sel)
    try:
        res = export_traces(ts, sel, roster_status(), labels, str(fmt_val).lower(), out_dir or (settings.reports_dir / "exports"))
    except ExportError as e:
        console.print(f"[bold red]Export failed:[/bold red] {e}")
        raise typer.Exit(code=1)
    console.print(f"Wrote {res.path.resolve()}", markup=False)
    console.print(f"records exported {res.n_exported}, skipped {res.n_skipped}, redacted {res.n_redacted}, missing telemetry {res.n_missing_telemetry}", markup=False)
    for w in res.warnings:
        console.print(f"WARNING: {w}", markup=False)


@app.command("api-preflight")
def api_preflight() -> None:
    """Report whether the API key is available WITHOUT showing it and WITHOUT sending any request."""
    import os
    import sys

    from runport.core.config import get_api_key_source, load_project_env
    from runport.models.registry import roster_status

    load_project_env()
    raw = os.environ.get("OPENROUTER_API_KEY")
    present = bool(raw and raw.strip())
    odd_whitespace = bool(raw) and raw != raw.strip()
    table = Table(title="API preflight (no request is sent; the key value is never shown)", show_header=True, header_style="bold magenta")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("OPENROUTER_API_KEY is set and non-empty", "[green]yes[/green]" if present else "[bold red]no[/bold red]")
    if present:
        table.add_row("Key has leading/trailing whitespace", "[yellow]yes (fix it)[/yellow]" if odd_whitespace else "no")
    table.add_row("Interactive terminal (needed for live approval)", "yes" if (sys.stdin.isatty() and sys.stdout.isatty()) else "[yellow]no: live runs would be refused[/yellow]")
    table.add_row("Source of the key", get_api_key_source())
    table.add_row("Network used by this command", "none")
    rows = roster_status()
    table.add_row("Participants READY / SMOKE_READY / BLOCKED",
                  f"{sum(r['readiness'] == 'READY' for r in rows)} / {sum(r['readiness'] == 'SMOKE_READY' for r in rows)} / {sum(r['readiness'] == 'BLOCKED' for r in rows)}")
    table.add_row("Confidential/unverified data allowed to any provider", "[bold red]no[/bold red] (strict privacy gate active)")
    console.print(table)
    if not present:
        console.print("Set it in your shell (e.g. export OPENROUTER_API_KEY=...) or in .env before a live run (never paste it into chat or commit it)", markup=False)
    raise typer.Exit(code=0 if present else 1)


@app.command(name="welcome")
def launch_welcome() -> None:
    """Launch the interactive developer-grade welcome screen."""
    run_launcher_loop()


@app.command(name="ui")
def launch_ui(
    web: bool = typer.Option(False, "--web", help="Launch the web dashboard instead of the terminal UI"),
    port: int = typer.Option(8000, help="Web server port (if --web is used)"),
) -> None:
    """Launch the interactive terminal UI (or web dashboard with --web)."""
    if web:
        import uvicorn
        console.print(f"[bold green]Starting Runport Web Dashboard on http://127.0.0.1:{port}[/bold green]")
        uvicorn.run("runport.api.app:create_app", factory=True, host="127.0.0.1", port=port)
    else:
        from runport.tui.app import run_tui
        run_tui()


@app.command(name="web")
def web_cmd(
    host: str = typer.Option("127.0.0.1", help="Host interface to bind to"),
    port: int = typer.Option(8000, help="Port to listen on"),
    reload: bool = typer.Option(False, help="Enable auto-reload for development"),
) -> None:
    """Start the Runport web dashboard and REST API service."""
    import uvicorn
    console.print(f"[bold green]Starting Runport Web Dashboard on http://{host}:{port}[/bold green]")
    uvicorn.run("runport.api.app:create_app", factory=True, host=host, port=port, reload=reload)


@app.command(name="interactive", hidden=True)
def launch_interactive() -> None:
    """Alias to launch the interactive terminal UI."""
    from runport.tui.app import run_tui
    run_tui()


def compute_sha256(filepath: Path) -> str:
    """Computes SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


# ---------------------------------------------------------------------------
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

    # 1. Dataset Overview Table
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

    # 2. Privacy & Governance Breakdown Table
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

    # 3. Leakage Findings
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

    # 4. Final Verdict
    if summary.is_valid:
        console.print(Panel(
            f"[bold green]✓ DATASET VALIDATION PASSED[/bold green]\n"
            f"Total Cases: {summary.total_cases} | Zero Leakage Detected | Confidentiality Invariants Satisfied",
            border_style="green",
        ))
    else:
        err_msg = "\n".join(f"• {e}" for e in summary.validation_errors)
        console.print(Panel(
            f"[bold red]✗ DATASET VALIDATION FAILED[/bold red]\n{err_msg}",
            border_style="red",
        ))
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# Model Evaluation & Benchmarking Subsystem (Phase 3)
# ---------------------------------------------------------------------------


@app.command(name="benchmark")
def run_benchmark(
    model_id: str = typer.Option(
        "google/gemini-3.5-flash-lite",
        "--model",
        "-m",
        help="Target candidate model ID to evaluate.",
    ),
    dataset_path: Path = typer.Option(
        Path("data/evaluation/synthetic_seed_eval.jsonl"),
        "--dataset",
        "-d",
        help="Path to evaluation dataset JSONL.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    split: str = typer.Option(
        "TEST",
        "--split",
        "-s",
        help="Evaluation split to benchmark: 'TEST', 'DEV', or 'ALL'.",
    ),
    live: bool = typer.Option(
        False,
        "--live",
        help="Send real requests to OpenRouter. Required: without it the command only explains what it would do and sends nothing.",
    ),
) -> None:
    """Benchmark a candidate model with REAL requests (typed approval required), tracked against the budget."""
    from runport.evaluation.runner import BenchmarkRunner
    from runport.schemas.evaluation import DatasetSplit

    model_id = getattr(model_id, "default", model_id) if hasattr(model_id, "default") else model_id
    dataset_path_val = getattr(dataset_path, "default", dataset_path) if hasattr(dataset_path, "default") else dataset_path
    dataset_path = Path(dataset_path_val) if not isinstance(dataset_path_val, Path) else dataset_path_val
    live = getattr(live, "default", live) if hasattr(live, "default") else live

    console.print(Panel(
        f"[bold cyan]Runport Model Evaluation Benchmark[/bold cyan]\n"
        f"Target Model:  [bold white]{model_id}[/bold white]\n"
        f"Dataset:       {dataset_path.name}\n"
        f"Mode:          [bold green]REAL REQUESTS[/bold green] (typed approval required)",
        expand=False,
    ))
    if not live:
        console.print("Nothing was sent. Add --live to request typed approval for real requests.", markup=False)
        raise typer.Exit(code=2)

    split_val = getattr(split, "default", split) if hasattr(split, "default") else split
    split_str = str(split_val).strip()
    target_split = None
    if split_str.upper() != "ALL":
        try:
            target_split = DatasetSplit(split_str.upper())
        except ValueError:
            console.print(f"[bold red]Error:[/bold red] Invalid split '{split_str}'. Choose TEST, DEV, or ALL.")
            raise typer.Exit(code=1)

    live_auth = _require_live_confirmation([model_id], dataset_path.name)
    runner = BenchmarkRunner()
    try:
        report = runner.run(
            model_id=model_id,
            dataset_path=dataset_path,
            split=target_split,
            live_authorization=live_auth,
        )
    except Exception as e:
        console.print(f"[bold red]Benchmark Failed:[/bold red] {e}")
        raise typer.Exit(code=1)

    # 1. Summary Metrics Table
    summary_table = Table(title="Benchmark Execution Summary", show_header=True, header_style="bold magenta")
    summary_table.add_column("Metric", style="dim")
    summary_table.add_column("Value", justify="right")
    summary_table.add_column("Benchmark Evaluation Context", style="italic")

    summary_table.add_row("Run Identifier", report.run_id, "Unique execution run ID stored in SQLite")
    summary_table.add_row("Evaluated Cases", f"{report.completed_cases} / {report.total_cases}", f"Split: {split.upper()}")
    summary_table.add_row("Mean Latency", f"{report.mean_latency_ms:.1f} ms", "End-to-end inference turnaround")
    summary_table.add_row("Mean Accuracy", f"{report.mean_accuracy * 100:.1f}%", "Factual overlap against ground truth citations")
    summary_table.add_row("Mean Groundedness", f"{report.mean_groundedness * 100:.1f}%", "Absence of unsupported hallucinations")
    summary_table.add_row("Overall Score", f"[bold green]{report.mean_overall_score * 100:.1f}%[/bold green]", "Weighted composite rubric score")
    summary_table.add_row("Run Spend (USD)", f"${report.total_cost_usd:.4f}", "Deducted and verified against budget ledger")
    console.print(summary_table)

    # 2. Case Results Table
    case_table = Table(title="Per-Case Performance Breakdown", show_header=True, header_style="bold blue")
    case_table.add_column("Case ID", style="cyan", width=12)
    case_table.add_column("Query Snippet", style="white", width=36)
    case_table.add_column("Latency", justify="right", width=10)
    case_table.add_column("Accuracy", justify="right", width=10)
    case_table.add_column("Grounded", justify="right", width=10)
    case_table.add_column("Overall", justify="right", style="bold", width=9)

    for r in report.results:
        q_snip = r["prompt"][:34] + ("..." if len(r["prompt"]) > 34 else "")
        case_table.add_row(
            r["case_id"],
            q_snip,
            f"{r['latency_ms']:.0f} ms",
            f"{r['accuracy'] * 100:.0f}%",
            f"{r['groundedness'] * 100:.0f}%",
            f"{r['overall_score'] * 100:.0f}%",
        )
    console.print(case_table)


@app.command(name="compare-runs")
def compare_runs(
    run_a: str = typer.Argument(..., help="Run ID of the baseline evaluation run."),
    run_b: str = typer.Argument(..., help="Run ID of the comparison evaluation run."),
) -> None:
    """Compare two evaluation benchmark runs side by side."""
    from runport.storage.db import DatabaseManager

    db = DatabaseManager()
    data_a = db.get_evaluation_run(run_a)
    data_b = db.get_evaluation_run(run_b)

    if not data_a:
        console.print(f"[bold red]Error:[/bold red] Run '{run_a}' not found in database.")
        raise typer.Exit(code=1)
    if not data_b:
        console.print(f"[bold red]Error:[/bold red] Run '{run_b}' not found in database.")
        raise typer.Exit(code=1)

    console.print(Panel(
        f"[bold cyan]Evaluation Run Comparison[/bold cyan]\n"
        f"Baseline Run (A):    [white]{run_a}[/white] ({data_a['model_id']})\n"
        f"Comparison Run (B):  [white]{run_b}[/white] ({data_b['model_id']})",
        expand=False,
    ))

    table = Table(title="Run Comparison & Performance Deltas", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="dim")
    table.add_column(f"Run A ({data_a['model_id'][:18]})", justify="right")
    table.add_column(f"Run B ({data_b['model_id'][:18]})", justify="right")
    table.add_column("Delta (B - A)", justify="right", style="bold")

    acc_a = float(data_a["mean_accuracy"])
    acc_b = float(data_b["mean_accuracy"])
    d_acc = acc_b - acc_a
    d_acc_str = f"[green]+{d_acc * 100:.1f}%[/green]" if d_acc >= 0 else f"[red]{d_acc * 100:.1f}%[/red]"

    lat_a = float(data_a["mean_latency_ms"])
    lat_b = float(data_b["mean_latency_ms"])
    d_lat = lat_b - lat_a
    d_lat_str = f"[green]{d_lat:+.1f} ms[/green]" if d_lat <= 0 else f"[yellow]{d_lat:+.1f} ms[/yellow]"

    sc_a = float(data_a["mean_overall_score"])
    sc_b = float(data_b["mean_overall_score"])
    d_sc = sc_b - sc_a
    d_sc_str = f"[green]+{d_sc * 100:.1f}%[/green]" if d_sc >= 0 else f"[red]{d_sc * 100:.1f}%[/red]"

    cost_a = Decimal(data_a["total_cost_usd"])
    cost_b = Decimal(data_b["total_cost_usd"])
    d_cost = cost_b - cost_a
    d_cost_str = f"${d_cost:+.4f}"

    table.add_row("Mean Accuracy", f"{acc_a * 100:.1f}%", f"{acc_b * 100:.1f}%", d_acc_str)
    table.add_row("Mean Groundedness", f"{float(data_a['mean_groundedness']) * 100:.1f}%", f"{float(data_b['mean_groundedness']) * 100:.1f}%", f"{(float(data_b['mean_groundedness']) - float(data_a['mean_groundedness'])) * 100:+.1f}%")
    table.add_row("Overall Score", f"{sc_a * 100:.1f}%", f"{sc_b * 100:.1f}%", d_sc_str)
    table.add_row("Mean Latency", f"{lat_a:.1f} ms", f"{lat_b:.1f} ms", d_lat_str)
    table.add_row("Total Run Spend", f"${cost_a:.4f}", f"${cost_b:.4f}", d_cost_str)
    table.add_row("Completed Cases", f"{data_a['completed_cases']}", f"{data_b['completed_cases']}", f"{data_b['completed_cases'] - data_a['completed_cases']:+d}")

    console.print(table)


# ---------------------------------------------------------------------------
# Decoupled RAG Benchmark Subcommand
# ---------------------------------------------------------------------------


@app.command("benchmark-rag")
def benchmark_rag(
    model: str = typer.Option(
        "google/gemini-3.5-flash-lite",
        "--model",
        "-m",
        help="Primary candidate model ID to evaluate.",
    ),
    dataset: Path = typer.Option(
        Path("data/evaluation/verified_rag_benchmark.jsonl"),
        "--dataset",
        "-d",
        help="Path to verified evaluation dataset JSONL.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    split: str = typer.Option(
        "TEST",
        "--split",
        "-s",
        help="Partition split to benchmark: 'TEST', 'DEV', or 'ALL'.",
    ),
    live: bool = typer.Option(
        False,
        "--live",
        help="Send real requests to OpenRouter. Required: without it the command only explains what it would do and sends nothing.",
    ),
    compare_with: Optional[str] = typer.Option(
        None,
        "--compare-with",
        "-c",
        help="Optional second candidate model ID for side-by-side RAG comparison.",
    ),
    top_k: int = typer.Option(
        2,
        "--top-k",
        "-k",
        help="Number of context chunks to retrieve per case (default 2).",
    ),
    exclude_defective: bool = typer.Option(
        True,
        "--exclude-defective/--include-all",
        help="Exclude known contradictory or incomplete records from the retrieval index (default True).",
    ),
) -> None:
    """Benchmark candidate models on decoupled retrieval, generation, and end-to-end RAG metrics."""
    from runport.dataset.manager import DatasetManager
    from runport.rag.retriever import KeywordBM25Retriever
    from runport.rag.runner import RAGBenchmarkRunner
    from runport.schemas.evaluation import DatasetSplit
    model = getattr(model, "default", model) if hasattr(model, "default") else model
    dataset_val = getattr(dataset, "default", dataset) if hasattr(dataset, "default") else dataset
    dataset = Path(dataset_val) if not isinstance(dataset_val, Path) else dataset_val
    split_val = getattr(split, "default", split) if hasattr(split, "default") else split
    split_clean = str(split_val).strip().upper()
    split_enum = DatasetSplit(split_clean) if split_clean in DatasetSplit.__members__ else DatasetSplit.UNASSIGNED
    live = getattr(live, "default", live) if hasattr(live, "default") else live
    top_k = getattr(top_k, "default", top_k) if hasattr(top_k, "default") else top_k
    compare_with = getattr(compare_with, "default", compare_with) if hasattr(compare_with, "default") else compare_with
    exclude_defective = getattr(exclude_defective, "default", exclude_defective) if hasattr(exclude_defective, "default") else exclude_defective

    # Real retrieval only: a BM25 index over the audited knowledge-base records. There is no mock or answer-leaking retriever.
    gen_kb_path = Path("data/audit/parsed_records_general_kb.jsonl")
    prog_kb_path = Path("data/audit/parsed_records_programmes_kb.jsonl")
    if not (gen_kb_path.exists() or prog_kb_path.exists()):
        console.print("[bold red]Audited knowledge-base records not found under data/audit/.[/bold red] Run `runport audit-kb` first; "
                      "the benchmark will not fall back to evaluation passages.")
        raise typer.Exit(code=1)
    retriever = KeywordBM25Retriever.from_parsed_kb(
        general_path=gen_kb_path if gen_kb_path.exists() else None,
        programmes_path=prog_kb_path if prog_kb_path.exists() else None,
        exclude_defective=exclude_defective,
    )
    manifest = getattr(retriever, "manifest", {})
    console.print(
        f"[dim]BM25 indexed {len(retriever.documents)} clean documents from audited KB records "
        f"(excluded {manifest.get('excluded_defective_count', 0)} defective records).[/dim]"
    )
    test_cases = DatasetManager.load_jsonl(dataset)
    leaked = retriever.verify_no_leakage(test_cases)
    if leaked:
        console.print(f"[bold red]WARNING: Evaluation data leakage detected for case IDs: {leaked}[/bold red]")

    console.print(Panel(
        f"[bold cyan]Runport End-to-End RAG Benchmark[/bold cyan]\n"
        f"[dim]Primary Model:[/dim]  [bold white]{model}[/bold white]\n"
        f"[dim]Retriever:[/dim]      [bold green]{retriever.__class__.__name__}[/bold green] (top_k: {top_k})\n"
        f"[dim]Dataset:[/dim]        {dataset.name} (Split: {split_clean})\n"
        f"[dim]Execution Mode:[/dim] [red]REAL REQUESTS[/red] (typed approval required)",
        expand=False,
    ))
    if not live:
        console.print("Nothing was sent. Add --live to request typed approval for real requests.", markup=False)
        raise typer.Exit(code=2)

    live_models = [model] + ([compare_with] if compare_with else [])
    live_auth = _require_live_confirmation(live_models, dataset.name)
    runner = RAGBenchmarkRunner(retriever=retriever, top_k=top_k)
    report_a = runner.run(model_id=model, dataset_path=dataset, split=split_enum, live_authorization=live_auth)

    # 1. Decoupled Summary Table
    summary_table = Table(title="Decoupled RAG Performance Summary", show_header=True, header_style="bold magenta")
    summary_table.add_column("Subsystem / Metric", style="cyan")
    summary_table.add_column("Value", justify="right", style="bold")
    summary_table.add_column("Evaluation Context", style="dim")

    summary_table.add_row("Total Evaluated Cases", f"{report_a.total_cases}", f"Split: {split_clean}")
    summary_table.add_row("Verified Ground Truth Cases", f"{report_a.verified_cases_count}", "Cases with verified source KB records")
    summary_table.add_row("Unresolved Abstention Cases", f"{report_a.unresolved_cases_count}", "Cases unsupported by KB expecting abstention")
    summary_table.add_row("Source Recall@k", f"[bold green]{report_a.mean_recall_at_k * 100:.1f}%[/bold green]", f"Relevant record retrieved in top-{top_k} (Verified only)")
    summary_table.add_row("Source Precision@k", f"{report_a.mean_precision_at_k * 100:.1f}%", f"Ratio of top-{top_k} records that are relevant")
    summary_table.add_row("Mean Reciprocal Rank (MRR)", f"[bold cyan]{report_a.mean_reciprocal_rank:.4f}[/bold cyan]", "1 / rank of first relevant record (Verified only)")
    summary_table.add_row("Verified Retrieval Hit Rate", f"[bold green]{report_a.verified_retrieval_hit_rate * 100:.1f}%[/bold green]", "Proportion of verified cases with >= 1 hit")
    summary_table.add_row("Abstention Accuracy", f"[bold yellow]{report_a.abstention_accuracy * 100:.1f}%[/bold yellow]", "Model successfully abstained on unsupported queries")
    summary_table.add_row("Retrieval Latency", f"{report_a.mean_retrieval_latency_ms:.1f} ms", "Isolated context search turnaround")
    summary_table.add_row("Answer Correctness", f"{report_a.mean_answer_correctness * 100:.1f}%", "Factual overlap against reference answer")
    summary_table.add_row("Groundedness (Faithfulness)", f"{report_a.mean_groundedness * 100:.1f}%", "Supported by context (hallucination check)")
    summary_table.add_row("Diagnostic Keyword Hit Rate", f"{report_a.diagnostic_keyword_hit_rate * 100:.1f}%", "Secondary exact keyword-substring match")
    summary_table.add_row("Generation Latency", f"{report_a.mean_generation_latency_ms:.1f} ms", "Isolated LLM inference turnaround")
    summary_table.add_row("End-to-End Latency", f"[bold yellow]{report_a.mean_e2e_latency_ms:.1f} ms[/bold yellow]", "Total user turnaround (Ret + Gen)")
    summary_table.add_row("Run Spend (USD)", f"${report_a.total_cost_usd:.4f}", "Tracked in budget ledger")

    console.print(summary_table)

    # 2. Failure Attribution Breakdown
    attr_table = Table(title="Failure Attribution Analysis", show_header=True, header_style="bold magenta")
    attr_table.add_column("Attribution Category", style="bold")
    attr_table.add_column("Count", justify="right")
    attr_table.add_column("% Share", justify="right")
    attr_table.add_column("Diagnosis / Implication", style="dim")

    tot = max(1, report_a.total_cases)
    for cat, cnt in report_a.failure_breakdown.items():
        pct = (cnt / tot) * 100
        if cat in ("SYSTEM_SUCCESS", "ABSTENTION_SUCCESS"):
            diag = "[green]Satisfied source grounding or correctly abstained[/green]"
        elif cat == "RETRIEVAL_FAILURE":
            diag = "[red]Retriever starved model of necessary context[/red]"
        elif cat in ("GENERATION_FAILURE", "OVERCONFIDENT_HALLUCINATION"):
            diag = "[yellow]Context available or absent, but model erred or hallucinated[/yellow]"
        else:
            diag = "[blue]Model answered correctly despite weak context[/blue]"
        attr_table.add_row(cat, str(cnt), f"{pct:.1f}%", diag)

    console.print(attr_table)

    # 3. Per-Case Performance Table
    case_table = Table(title="Per-Case Decoupled Breakdown", show_header=True, header_style="bold blue")
    case_table.add_column("Case ID", style="cyan", width=16)
    case_table.add_column("Status", width=14)
    case_table.add_column("Target Record(s)", width=16)
    case_table.add_column("Retrieved Record(s)", width=18)
    case_table.add_column("Recall@k", justify="right", width=9)
    case_table.add_column("MRR", justify="right", width=8)
    case_table.add_column("Attribution", style="bold", width=22)

    for c in report_a.case_results:
        status_style = "[green]VERIFIED[/green]" if c.source_status == "SOURCE_VERIFIED" else "[yellow]UNRESOLVED[/yellow]"
        targets = ", ".join(c.relevant_record_ids) if c.relevant_record_ids else "(None - Abstain)"
        retrieved_recs = ", ".join(c.retrieved_record_ids) if c.retrieved_record_ids else "(None)"
        
        attr_style = (
            "[green]SUCCESS[/green]" if c.failure_attribution in ("SYSTEM_SUCCESS", "ABSTENTION_SUCCESS")
            else f"[red]{c.failure_attribution}[/red]"
        )
        case_table.add_row(
            c.case_id,
            status_style,
            targets,
            retrieved_recs,
            f"{c.recall_at_k * 100:.0f}%" if c.relevant_record_ids else "N/A",
            f"{c.reciprocal_rank:.2f}" if c.relevant_record_ids else "N/A",
            attr_style,
        )

    console.print(case_table)

    # Optional Multi-Model Comparison
    if compare_with:
        console.print(Panel(
            f"[bold cyan]Running Side-by-Side Model Comparison[/bold cyan]\n"
            f"[dim]Comparison Candidate:[/dim] [bold white]{compare_with}[/bold white]",
            expand=False,
        ))
        runner_b = RAGBenchmarkRunner(retriever=retriever)
        report_b = runner_b.run(model_id=compare_with, dataset_path=dataset, split=split_enum, live_authorization=live_auth)

        comp_table = Table(title=f"Comparative Benchmark: {model} vs {compare_with}", show_header=True, header_style="bold magenta")
        comp_table.add_column("Metric", style="cyan")
        comp_table.add_column(f"{model[:18]} (A)", justify="right")
        comp_table.add_column(f"{compare_with[:18]} (B)", justify="right")
        comp_table.add_column("Delta (B - A)", justify="right")

        def _fmt_delta(delta: float, is_pct: bool = False, reverse: bool = False) -> str:
            sign = "+" if delta > 0 else ""
            txt = f"{sign}{delta * 100:.1f}%" if is_pct else f"{sign}{delta:.1f}"
            if delta == 0:
                return f"[dim]{txt}[/dim]"
            is_good = (delta > 0) if not reverse else (delta < 0)
            return f"[green]{txt}[/green]" if is_good else f"[red]{txt}[/red]"

        comp_table.add_row("Answer Correctness", f"{report_a.mean_answer_correctness * 100:.1f}%", f"{report_b.mean_answer_correctness * 100:.1f}%", _fmt_delta(report_b.mean_answer_correctness - report_a.mean_answer_correctness, is_pct=True))
        comp_table.add_row("Groundedness", f"{report_a.mean_groundedness * 100:.1f}%", f"{report_b.mean_groundedness * 100:.1f}%", _fmt_delta(report_b.mean_groundedness - report_a.mean_groundedness, is_pct=True))
        comp_table.add_row("Generation Latency", f"{report_a.mean_generation_latency_ms:.1f} ms", f"{report_b.mean_generation_latency_ms:.1f} ms", _fmt_delta(report_b.mean_generation_latency_ms - report_a.mean_generation_latency_ms, reverse=True))
        comp_table.add_row("End-to-End Latency", f"{report_a.mean_e2e_latency_ms:.1f} ms", f"{report_b.mean_e2e_latency_ms:.1f} ms", _fmt_delta(report_b.mean_e2e_latency_ms - report_a.mean_e2e_latency_ms, reverse=True))
        comp_table.add_row("Total Run Spend", f"${report_a.total_cost_usd:.4f}", f"${report_b.total_cost_usd:.4f}", f"${report_b.total_cost_usd - report_a.total_cost_usd:+.4f}")

        console.print(comp_table)


# ---------------------------------------------------------------------------
# Langfuse Trace Diagnostic Subcommand
# ---------------------------------------------------------------------------


@app.command("import-traces")
def import_traces(
    export_file: Path = typer.Argument(
        ...,
        help="Path to Langfuse JSON or CSV trace export file.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Directory to export diagnostic CSV and Markdown reports (e.g. reports/).",
    ),
    min_confidence: float = typer.Option(
        0.50,
        "--min-confidence",
        "-c",
        help="Minimum confidence threshold for candidate hypotheses.",
    ),
) -> None:
    """Ingest redacted Langfuse RAG traces and diagnose candidate failure modes."""
    from runport.traces.analyzer import TraceDiagnosticAnalyzer
    from runport.traces.importer import TraceImporter
    from runport.traces.models import FailureCategory
    from runport.traces.reporter import DiagnosticReporter

    console.print(Panel(
        f"[bold cyan]Langfuse Trace Ingestion & Diagnostic Analyzer[/bold cyan]\n"
        f"[dim]File:[/dim] [bold white]{export_file.name}[/bold white]\n"
        f"[dim]Min Confidence:[/dim] [yellow]{min_confidence:.0%}[/yellow]",
        expand=False,
    ))

    try:
        traces = TraceImporter.load_from_file(export_file)
    except Exception as e:
        console.print(f"[bold red]Failed to load trace export:[/bold red] {e}")
        raise typer.Exit(code=1)

    if not traces:
        console.print("[yellow]No traces found in specified export file.[/yellow]")
        return

    analyzer = TraceDiagnosticAnalyzer(min_confidence=min_confidence)
    report = analyzer.analyze_batch(traces)

    # 1. Summary Table
    table_sum = Table(title="Trace Batch Summary", show_header=True, header_style="bold magenta")
    table_sum.add_column("Metric", style="dim")
    table_sum.add_column("Value", justify="right", style="bold")
    table_sum.add_column("Operational Context", style="italic")

    table_sum.add_row("Total Ingested Traces", str(report.total_traces), "Successfully validated offline")
    table_sum.add_row("Diagnosed Failures", str(report.diagnosed_failures), "Identified candidate failure hypotheses")
    table_sum.add_row("Mean Latency", f"{report.mean_latency_ms:.1f} ms", "End-to-end trace turnaround")
    table_sum.add_row("Total Token Footprint", f"{report.total_tokens:,}", "Aggregated prompt and completion tokens")

    console.print(table_sum)

    # 2. Failure Distribution Table
    table_dist = Table(title="Failure Category Distribution", show_header=True, header_style="bold magenta")
    table_dist.add_column("Failure Category", style="cyan")
    table_dist.add_column("Candidate Count", justify="right")
    table_dist.add_column("% Share", justify="right")
    table_dist.add_column("Severity / Priority", justify="center")

    for cat_name, count in report.category_counts.items():
        pct = (count / max(1, report.total_traces)) * 100
        if cat_name == FailureCategory.ROUTING_FAILURE.value:
            prio = "[bold red]HIGH[/bold red]"
        elif cat_name == FailureCategory.RETRIEVAL_FAILURE.value:
            prio = "[bold yellow]HIGH[/bold yellow]"
        elif cat_name == FailureCategory.SOURCE_KNOWLEDGE_FAILURE.value:
            prio = "[bold magenta]KB DEFECT[/bold magenta]"
        elif cat_name == FailureCategory.GENERATION_FAILURE.value:
            prio = "[bold blue]MEDIUM[/bold blue]"
        else:
            prio = "[green]HEALTHY[/green]"

        table_dist.add_row(cat_name, str(count), f"{pct:.1f}%", prio)

    console.print(table_dist)

    # 3. Detailed Diagnoses Table
    table_diag = Table(title="Candidate Diagnostic Hypotheses", show_header=True, header_style="bold magenta")
    table_diag.add_column("Trace ID", style="cyan", no_wrap=True)
    table_diag.add_column("Category", style="bold")
    table_diag.add_column("Conf.", justify="right")
    table_diag.add_column("Hypothesis Snippet", style="white")
    table_diag.add_column("Suggested Action", style="green")

    for d in report.diagnoses:
        if d.category != FailureCategory.NO_FAILURE_DETECTED:
            table_diag.add_row(
                d.trace_id,
                d.category.value,
                f"{d.confidence:.0%}",
                d.hypothesis[:65] + "..." if len(d.hypothesis) > 65 else d.hypothesis,
                d.suggested_action[:45] + "..." if len(d.suggested_action) > 45 else d.suggested_action,
            )

    if table_diag.rows:
        console.print(table_diag)

    # 4. Export reports if requested
    if output_dir:
        out_path = Path(output_dir)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_file = out_path / f"trace_diagnoses_{ts}.csv"
        md_file = out_path / f"trace_diagnoses_{ts}.md"
        DiagnosticReporter.export_csv(report, csv_file)
        DiagnosticReporter.export_markdown(report, md_file)
        console.print(f"\n[green]Diagnostic reports generated successfully:[/green]")
        console.print(f"  • CSV: [bold]{csv_file}[/bold]")
        console.print(f"  • Markdown: [bold]{md_file}[/bold]")


# ---------------------------------------------------------------------------
# Budget Subcommands
# ---------------------------------------------------------------------------


@budget_app.command(name="reconcile")
def budget_reconcile(
    transaction_id: str = typer.Option(..., "--transaction-id", "-t", help="Unresolved ledger entry to resolve."),
    amount_usd: str = typer.Option(..., "--amount-usd", "-a", help="Real amount in USD read from the provider dashboard."),
    note: str = typer.Option("", "--note", help="Optional note, for example the dashboard date."),
) -> None:
    """Resolve an unresolved-spend entry with an amount you read from the provider dashboard. Live runs stay blocked until none remain."""
    from decimal import Decimal, InvalidOperation

    try:
        amount = Decimal(amount_usd)
        if amount < 0:
            raise InvalidOperation
    except InvalidOperation:
        console.print("[bold red]--amount-usd must be a non-negative number[/bold red]")
        raise typer.Exit(code=1)
    service = BudgetService()
    service.db.init_db()
    try:
        service.db.reconcile_transaction(transaction_id, amount, note)
    except (KeyError, ValueError) as e:
        console.print(f"[bold red]{e}[/bold red]")
        raise typer.Exit(code=1)
    left = len(service.unresolved())
    console.print(f"Reconciled {transaction_id} at ${amount:.6f}. Unresolved entries remaining: {left}.", markup=False)


@budget_app.command(name="purge-simulated")
def budget_purge_simulated() -> None:
    """Delete all simulated (dry-run) ledger rows and stored dry-run runs. The database is copied first; real entries are never touched."""
    service = BudgetService()
    result = service.db.purge_simulated(backup=True)
    console.print(f"Removed {result['ledger_rows']} simulated ledger rows, {result['runs']} dry-run runs and {result['results']} stored results.", markup=False)
    console.print(f"Backup of the previous database: {result['backup'] or 'none (no database file)'}", markup=False)


@budget_app.command(name="audit")
def budget_audit_cmd() -> None:
    """Reconcile the ledger with the stored results (read-only). Explains ledger total versus per-plan guard cost. Writes reports/budget_reconciliation_*.md/.json."""
    import json
    from datetime import datetime, timezone

    from runport.core.config import settings
    from runport.observability import budget_audit as ba

    service = BudgetService()
    service.db.init_db()
    a = ba.audit(service.db.db_path, service.policy, settings.reports_dir, settings.data_dir / "benchmarks")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    md, js = settings.reports_dir / f"budget_reconciliation_{stamp}.md", settings.reports_dir / f"budget_reconciliation_{stamp}.json"
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    js.write_text(json.dumps(a, indent=2) + "\n")
    md.write_text(ba.audit_markdown(a))
    console.print(f"Ledger counted: ${a['ledger_total_counted_usd']}  remaining total ${a['remaining_usd']['total']}  pilot ceiling ${a['ceilings_usd']['pilot']}  unresolved {a['unresolved_entries']}", markup=False)
    for g in a["groups"]:
        console.print(f"  {g['group']:<28}ledger ${g['ledger_usd']:<10} records ${g['records_recorded_cost_usd']:<10} guard ${g['guard_from_records_usd']:<10} ledger=records {g['ledger_equals_records']}", markup=False)
    console.print(f"RECONCILED: {a['reconciled']}   report: {md.resolve()}", markup=False)
    raise typer.Exit(code=0 if a["reconciled"] else 1)


@budget_app.command(name="policy")
def budget_policy_cmd() -> None:
    """Show the effective ceilings and the audit trail of operator-authorized pilot-ceiling changes."""
    from runport.core import budget_policy as bp
    from runport.core.config import settings

    eff = bp.effective_policy(settings.budget, settings.data_dir)
    console.print(f"effective: total ${eff.total_budget_usd}  pilot ${eff.pilot_budget_usd}  per run ${eff.per_run_ceiling_usd}  per case ${eff.per_case_ceiling_usd}   (defaults: pilot ${settings.budget.pilot_budget_usd})", markup=False)
    for h in bp.history(settings.data_dir):
        console.print(f"  {h['at']}  {h['operator']}: pilot ${h['previous_pilot_budget_usd']} -> ${h['new_pilot_budget_usd']}  (total ${h['total_budget_usd']}; ledger counted ${h['ledger_total_spent_usd']} at the time)", markup=False)


@budget_app.command(name="raise-pilot-ceiling")
def budget_raise_pilot(to: str = typer.Option(..., "--to", help="New pilot ceiling in USD (never above the total lifetime ceiling)."),
                       operator: str = typer.Option(..., "--operator", help="Your name, recorded in the audit trail.")) -> None:
    """Operator-authorized pilot-ceiling change with an interactive typed phrase. The total, per-run and per-case ceilings and the ledger are untouched."""
    from decimal import Decimal, InvalidOperation

    from runport.core import budget_policy as bp
    from runport.core.config import settings
    from runport.providers.base import LiveNotAuthorizedError

    try:
        new = Decimal(to)
    except InvalidOperation:
        console.print(f"[bold red]Invalid amount:[/bold red] {to}")
        raise typer.Exit(code=1)
    service = BudgetService()
    st = service.get_status()
    try:
        entry = bp.raise_pilot_ceiling(settings.data_dir, settings.budget, new, operator=operator, ledger_total_spent=st.cumulative_spend_usd, ledger_pilot_spent=st.pilot_spend_usd,
                                       echo=lambda line: console.print(line, markup=False, highlight=False))
    except (LiveNotAuthorizedError, bp.PolicyError) as e:
        console.print(f"[bold red]Not changed:[/bold red] {e}")
        raise typer.Exit(code=1)
    console.print(f"Pilot ceiling is now ${entry['new_pilot_budget_usd']} (recorded in {bp.policy_path(settings.data_dir)}). Total ${entry['total_budget_usd']}, per-run ${entry['per_run_ceiling_usd']}, per-case ${entry['per_case_ceiling_usd']} unchanged.", markup=False)


@budget_app.command(name="status")
def budget_status() -> None:
    """Display current spend ledger, remaining balances, and local policy ceilings."""
    service = BudgetService()
    status = service.get_status()

    console.print(Panel("[bold cyan]Runport — Budget Status[/bold cyan]", expand=False))
    console.print("[yellow]NOTE: Ceilings below are local experiment tracking policies, NOT provider-enforced account limits.[/yellow]\n")

    table = Table(title="Spend & Policy Overview", show_header=True, header_style="bold magenta")
    table.add_column("Budget Metric", style="dim")
    table.add_column("Configured Ceiling", justify="right")
    table.add_column("Current Spend", justify="right")
    table.add_column("Remaining Balance", justify="right", style="bold")
    table.add_column("Status", justify="center")

    pilot_status_str = "[bold red]EXHAUSTED[/bold red]" if status.is_pilot_exhausted else "[green]ACTIVE[/green]"
    total_status_str = "[bold red]EXHAUSTED[/bold red]" if status.is_total_exhausted else "[green]ACTIVE[/green]"

    table.add_row(
        "Initial Pilot Budget",
        f"${status.pilot_ceiling_usd:.4f}",
        f"${status.pilot_spend_usd:.4f}",
        f"${status.remaining_pilot_usd:.4f}",
        pilot_status_str,
    )
    table.add_row(
        "Total Experiment Ceiling",
        f"${status.total_ceiling_usd:.4f}",
        f"${status.cumulative_spend_usd:.4f}",
        f"${status.remaining_total_usd:.4f}",
        total_status_str,
    )
    console.print(table)
    if status.simulated_spend_usd > 0:  # only legacy rows from before simulated runs stopped being recorded
        console.print(f"[dim]Legacy simulated entries (never counted against any ceiling): ${status.simulated_spend_usd:.6f}[/dim]")
    if status.spend_by_basis:
        console.print("[dim]Booked spend by basis: " + ", ".join(f"{k} ${v:.6f}" for k, v in sorted(status.spend_by_basis.items())) + "[/dim]")
    if status.unresolved_spend_count:
        console.print(f"[bold red]UNRESOLVED SPEND: {status.unresolved_spend_count} request(s) have unknown cost. Live runs are blocked until you run "
                      "`runport budget reconcile --transaction-id ... --amount-usd ...`.[/bold red]")
        for u in service.unresolved():
            console.print(f"  {u['transaction_id']}  {u['model_id']}", markup=False)
    console.print("")

    rule_table = Table(title="Per-Execution Safety Rules", show_header=True, header_style="bold blue")
    rule_table.add_column("Safety Rule", style="cyan")
    rule_table.add_column("Limit (USD)", justify="right")
    rule_table.add_column("Enforcement Action", style="italic")

    rule_table.add_row("Max Single Run Spend", f"${status.per_run_ceiling_usd:.4f}", "Preflight check rejects run if exceeded")
    rule_table.add_row("Max Single Case Spend", f"${status.per_case_ceiling_usd:.4f}", "Per-case circuit breaker halts run")
    rule_table.add_row("Execution Mode", "Real requests only", "Typed approval of the exact plan; interactive terminal required")
    console.print(rule_table)

    if status.recent_transactions:
        tx_table = Table(title="Recent Ledger Transactions", show_header=True, header_style="bold green")
        tx_table.add_column("Timestamp (UTC)", style="dim")
        tx_table.add_column("Model ID", style="cyan")
        tx_table.add_column("Provider", style="magenta")
        tx_table.add_column("Amount (USD)", justify="right")
        tx_table.add_column("Type")
        tx_table.add_column("Description", style="italic")

        for tx in status.recent_transactions:
            basis = tx.get("cost_basis") or "UNSPECIFIED"
            tx_type = ("[yellow]PRE-RUN ESTIMATE[/yellow]" if tx["is_preflight_estimate"] else "[dim]LEGACY SIMULATED[/dim]" if tx.get("is_simulated")
                       else "[bold red]UNRESOLVED[/bold red]" if tx.get("is_unresolved")
                       else "[bold green]ACTUAL[/bold green]" if basis in ("PROVIDER_REPORTED", "RECONCILED")
                       else "[yellow]ESTIMATED[/yellow]" if basis == "ESTIMATED_FROM_CATALOG" else f"[dim]{basis}[/dim]")
            tx_table.add_row(
                tx["timestamp"][:19].replace("T", " "),
                tx["model_id"],
                tx["provider"],
                f"${Decimal(tx['amount_micros'])/Decimal('1000000'):.4f}",
                tx_type,
                tx["description"],
            )
        console.print(tx_table)
    else:
        console.print("[dim]No paid transactions recorded yet. Spend ledger is at baseline ($0.0000).[/dim]")


# ---------------------------------------------------------------------------
# Models Subcommands
# ---------------------------------------------------------------------------


@models_app.command(name="list")
def models_list() -> None:
    """List the comparison participants (same view as `models roster`)."""
    models_roster()


if __name__ == "__main__":
    app()

