"""Trace export and Langfuse trace ingestion CLI commands."""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def register_trace_commands(app: typer.Typer) -> None:
    @app.command("trace")
    def view_trace(
        trace_id: str = typer.Argument(..., help="Trace ID to view (e.g. tr-1234...)"),
    ) -> None:
        """Inspect a canonical trace execution tree and span waterfall."""
        from runport.core.config import settings
        from runport.storage.db import DatabaseManager
        from runport.traces.repository import TraceRepository
        from runport.tui.traces_view import render_trace_panel, render_trace_tree

        db = DatabaseManager(settings.db_path)
        db.init_db()
        repo = TraceRepository(db=db)

        trace = repo.get_trace(trace_id, include_spans=True)
        if not trace:
            console.print(f"[bold red]Trace '{trace_id}' not found.[/bold red]")
            raise typer.Exit(code=1)

        console.print(render_trace_panel(trace))
        console.print()
        console.print(render_trace_tree(trace))

    @app.command("traces")
    def list_traces_cmd(
        run_id: Optional[str] = typer.Option(None, "--run", "-r", help="Filter by evaluation run ID"),
        case_id: Optional[str] = typer.Option(None, "--case", "-c", help="Filter by benchmark case ID"),
        limit: int = typer.Option(20, "--limit", "-n", help="Maximum number of traces to list"),
    ) -> None:
        """List stored canonical traces from benchmark runs."""
        from runport.core.config import settings
        from runport.storage.db import DatabaseManager
        from runport.traces.repository import TraceRepository
        from runport.tui.traces_view import render_traces_table

        db = DatabaseManager(settings.db_path)
        db.init_db()
        repo = TraceRepository(db=db)

        if run_id and case_id:
            traces = repo.get_traces_for_case(run_id, case_id, include_spans=True)
        elif run_id:
            traces = repo.get_traces_for_run(run_id, include_spans=True)
        else:
            traces = repo.list_traces(limit=limit, include_spans=True)

        if not traces:
            console.print("[dim]No canonical traces found matching criteria.[/dim]")
            return

        console.print(render_traces_table(traces))

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
        if task_val is not None and str(task_val).upper() not in ("CLASSIFICATION", "BINARY", "RAG", "TASK_A", "TASK_B"):
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
        console.print(
            f"records exported {res.n_exported}, skipped {res.n_skipped}, redacted {res.n_redacted}, missing telemetry {res.n_missing_telemetry}", markup=False
        )
        for w in res.warnings:
            console.print(f"WARNING: {w}", markup=False)

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

        console.print(
            Panel(
                f"[bold cyan]Langfuse Trace Ingestion & Diagnostic Analyzer[/bold cyan]\n"
                f"[dim]File:[/dim] [bold white]{export_file.name}[/bold white]\n"
                f"[dim]Min Confidence:[/dim] [yellow]{min_confidence:.0%}[/yellow]",
                expand=False,
            )
        )

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

        table_sum = Table(title="Trace Batch Summary", show_header=True, header_style="bold magenta")
        table_sum.add_column("Metric", style="dim")
        table_sum.add_column("Value", justify="right", style="bold")
        table_sum.add_column("Operational Context", style="italic")

        table_sum.add_row("Total Ingested Traces", str(report.total_traces), "Successfully validated offline")
        table_sum.add_row("Diagnosed Failures", str(report.diagnosed_failures), "Identified candidate failure hypotheses")
        table_sum.add_row(
            "Mean Latency",
            f"{report.mean_latency_ms:.1f} ms" if report.mean_latency_ms is not None else "unavailable",
            f"End-to-end trace turnaround ({report.traces_missing_latency} trace(s) did not report it)",
        )
        table_sum.add_row(
            "Total Token Footprint",
            f"{report.total_tokens:,}" if report.total_tokens is not None else "unavailable",
            f"Reported tokens only ({report.traces_missing_tokens} trace(s) did not report them)",
        )

        console.print(table_sum)

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

    @app.command("import-otlp")
    def import_otlp_cmd(
        file_path: Path = typer.Argument(
            ...,
            help="Path to OpenTelemetry OTLP JSON trace file.",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ) -> None:
        """Ingest OpenTelemetry / OpenInference OTLP JSON traces into canonical storage."""
        from runport.core.config import settings
        from runport.storage.db import DatabaseManager
        from runport.traces.otlp import OtlpIngester
        from runport.traces.repository import TraceRepository

        db = DatabaseManager(settings.db_path)
        db.init_db()
        repo = TraceRepository(db=db)

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            traces = OtlpIngester.ingest_to_repository(content, repo)
        except Exception as e:
            console.print(f"[bold red]Failed to ingest OTLP trace file:[/bold red] {e}")
            raise typer.Exit(code=1)

        total_spans = sum(len(t.spans) for t in traces)
        console.print(f"[bold green]Successfully ingested {len(traces)} trace(s) and {total_spans} span(s) from {file_path.name}[/bold green]")

    @app.command("export-otlp")
    def export_otlp_cmd(
        trace_id: str = typer.Argument(..., help="Trace ID to export in OTLP format"),
        out_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Destination file path (stdout if omitted)"),
    ) -> None:
        """Export a canonical trace in standard OpenTelemetry OTLP JSON format."""
        import json
        from runport.core.config import settings
        from runport.storage.db import DatabaseManager
        from runport.traces.otlp import OtlpExporter
        from runport.traces.repository import TraceRepository

        db = DatabaseManager(settings.db_path)
        db.init_db()
        repo = TraceRepository(db=db)

        trace = repo.get_trace(trace_id, include_spans=True)
        if not trace:
            console.print(f"[bold red]Trace '{trace_id}' not found.[/bold red]")
            raise typer.Exit(code=1)

        otlp_payload = OtlpExporter.export_trace(trace)
        json_str = json.dumps(otlp_payload, indent=2)

        if out_file:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(json_str, encoding="utf-8")
            console.print(f"[bold green]Exported trace '{trace_id}' to {out_file}[/bold green]")
        else:
            console.print_json(json_str)

    @app.command("export-langfuse")
    def export_langfuse_cmd(
        trace_id: str = typer.Argument(..., help="Trace ID to export in Langfuse format"),
        out_file: Optional[Path] = typer.Option(None, "--output", "-o", help="Destination file path (stdout if omitted)"),
    ) -> None:
        """Export a canonical trace in standard Langfuse v2 batch format."""
        import json
        from runport.core.config import settings
        from runport.storage.db import DatabaseManager
        from runport.traces.langfuse import LangfuseExporter
        from runport.traces.repository import TraceRepository

        db = DatabaseManager(settings.db_path)
        db.init_db()
        repo = TraceRepository(db=db)

        trace = repo.get_trace(trace_id, include_spans=True)
        if not trace:
            console.print(f"[bold red]Trace '{trace_id}' not found.[/bold red]")
            raise typer.Exit(code=1)

        payload = LangfuseExporter.export_trace(trace)
        json_str = json.dumps(payload, indent=2)

        if out_file:
            out_file.parent.mkdir(parents=True, exist_ok=True)
            out_file.write_text(json_str, encoding="utf-8")
            console.print(f"[bold green]Exported trace '{trace_id}' to {out_file} (Langfuse format)[/bold green]")
        else:
            console.print_json(json_str)

    @app.command("import-langfuse")
    def import_langfuse_cmd(
        file_path: Path = typer.Argument(
            ...,
            help="JSON file containing Langfuse batch payload or trace export",
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
        ),
    ) -> None:
        """Ingest traces from a Langfuse v2 JSON payload into canonical storage."""
        import json
        from runport.core.config import settings
        from runport.storage.db import DatabaseManager
        from runport.traces.langfuse import LangfuseIngester
        from runport.traces.repository import TraceRepository

        db = DatabaseManager(settings.db_path)
        db.init_db()
        repo = TraceRepository(db=db)

        try:
            content = json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as e:
            console.print(f"[bold red]Failed to parse JSON file:[/bold red] {e}")
            raise typer.Exit(code=1)

        try:
            traces = LangfuseIngester.ingest_to_repository(content, repo)
        except Exception as e:
            console.print(f"[bold red]Failed to ingest Langfuse trace file:[/bold red] {e}")
            raise typer.Exit(code=1)

        total_spans = sum(len(t.spans) for t in traces)
        console.print(f"[bold green]Successfully ingested {len(traces)} trace(s) and {total_spans} span(s) from {file_path.name}[/bold green]")
