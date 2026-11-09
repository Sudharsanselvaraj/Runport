"""Rich terminal UI components for visualizing canonical traces, spans, and execution trees.

Milestone 2 - Phase 4: Trace Visualization.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from runport.traces.domain import Span, SpanKind, SpanStatus, Trace


KIND_STYLES: Dict[SpanKind, str] = {
    SpanKind.LLM: "bold bright_blue",
    SpanKind.TOOL: "bold yellow",
    SpanKind.RETRIEVAL: "bold magenta",
    SpanKind.WORKFLOW_STEP: "bold cyan",
    SpanKind.AGENT: "bold green",
    SpanKind.HANDOFF: "bold purple",
    SpanKind.RERANK: "bold blue",
    SpanKind.ROUTER: "bold bright_cyan",
    SpanKind.OTHER: "dim white",
}

STATUS_ICONS: Dict[SpanStatus, str] = {
    SpanStatus.OK: "[bold green]✓[/bold green]",
    SpanStatus.ERROR: "[bold red]✗[/bold red]",
    SpanStatus.TIMEOUT: "[bold yellow]⏳[/bold yellow]",
    SpanStatus.CANCELLED: "[bold red]⊘[/bold red]",
    SpanStatus.UNSET: "[dim]•[/dim]",
}


def _format_span_label(span: Span, is_highlighted: bool = False) -> Text:
    """Renders a single span node text with kind badge, status icon, and telemetry."""
    text = Text()

    # Highlight marker
    if is_highlighted:
        text.append("▶ ", style="bold bright_white")

    # Status icon
    if span.status == SpanStatus.OK:
        text.append("✓ ", style="bold green")
    elif span.status == SpanStatus.ERROR:
        text.append("✗ ", style="bold red")
    elif span.status == SpanStatus.TIMEOUT:
        text.append("⏳ ", style="bold yellow")
    elif span.status == SpanStatus.CANCELLED:
        text.append("⊘ ", style="bold red")
    else:
        text.append("• ", style="dim")

    # Kind badge
    kind_style = KIND_STYLES.get(span.kind, "dim white")
    text.append(f"[{span.kind.value.upper()}] ", style=kind_style)

    # Span Name
    text.append(span.name, style="bold white")

    # Duration
    if span.duration_ms is not None:
        text.append(f"  {span.duration_ms:.1f}ms", style="cyan")
    else:
        text.append("  —", style="dim")

    # Tokens
    if span.prompt_tokens is not None or span.completion_tokens is not None:
        p = f"{span.prompt_tokens}" if span.prompt_tokens is not None else "—"
        c = f"{span.completion_tokens}" if span.completion_tokens is not None else "—"
        text.append(f"  ({p}↑ {c}↓)", style="dim white")

    # Cost
    if span.cost_usd is not None:
        basis = f" {span.cost_basis}" if span.cost_basis else ""
        text.append(f"  ${span.cost_usd}{basis}", style="green")

    # Error details
    if span.error:
        err_msg = span.error[:60] + "..." if len(span.error) > 60 else span.error
        text.append(f"  [ERROR: {err_msg}]", style="bold red")

    # Key attributes preview (e.g. tool arguments or retrieval query)
    attrs = span.attributes or {}
    if span.kind == SpanKind.TOOL and "arguments" in attrs:
        args_str = str(attrs["arguments"])
        if len(args_str) > 50:
            args_str = args_str[:47] + "..."
        text.append(f"  args={args_str}", style="dim")
    elif span.kind == SpanKind.RETRIEVAL:
        chunks_count = attrs.get("chunks_count") or (len(attrs["chunks"]) if "chunks" in attrs else None)
        if chunks_count is not None:
            text.append(f"  chunks={chunks_count}", style="dim")

    return text


def render_trace_tree(trace: Trace, highlight_span_id: Optional[str] = None) -> Tree:
    """Constructs a Rich Tree visualizing the hierarchical parent-child span waterfall."""
    status_style = "green" if trace.status == SpanStatus.OK else "red" if trace.status == SpanStatus.ERROR else "yellow"
    root_label = Text()
    root_label.append("Trace: ", style="bold")
    root_label.append(trace.name, style="bold cyan")
    root_label.append(f" [{trace.trace_id}]", style="dim")
    root_label.append(f" [{trace.status.value.upper()}]", style=f"bold {status_style}")

    tree = Tree(root_label)

    if not trace.spans:
        tree.add(Text("  No spans recorded in this trace", style="dim italic"))
        return tree

    # Map children per parent
    children_map: Dict[Optional[str], List[Span]] = {}
    for span in trace.spans:
        parent = span.parent_span_id
        if parent not in children_map:
            children_map[parent] = []
        children_map[parent].append(span)

    def _add_children(node: Any, parent_id: Optional[str]) -> None:
        for span in children_map.get(parent_id, []):
            is_hl = highlight_span_id is not None and span.span_id == highlight_span_id
            label = _format_span_label(span, is_highlighted=is_hl)
            sub_node = node.add(label)
            _add_children(sub_node, span.span_id)

    # Add root spans
    _add_children(tree, None)

    return tree


def render_trace_panel(trace: Trace) -> Panel:
    """Renders a summary card containing trace metadata and operational telemetry."""
    status_str = (
        f"[bold green]OK[/bold green]"
        if trace.status == SpanStatus.OK
        else (
            f"[bold red]{trace.status.value.upper()}[/bold red]"
            if trace.status == SpanStatus.ERROR
            else f"[bold yellow]{trace.status.value.upper()}[/bold yellow]"
        )
    )

    # Compute duration if timestamps available
    duration_str = "—"
    if trace.start_time and trace.end_time:
        duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000.0
        duration_str = f"{duration_ms:.1f} ms"

    tool_spans = sum(1 for s in trace.spans if s.kind == SpanKind.TOOL)
    llm_spans = sum(1 for s in trace.spans if s.kind == SpanKind.LLM)
    ret_spans = sum(1 for s in trace.spans if s.kind == SpanKind.RETRIEVAL)
    err_spans = sum(1 for s in trace.spans if s.status in (SpanStatus.ERROR, SpanStatus.TIMEOUT))

    table = Table.grid(padding=(0, 2))
    table.add_column("Field", style="dim", justify="right")
    table.add_column("Value", style="bold")
    table.add_column("Field2", style="dim", justify="right")
    table.add_column("Value2", style="bold")

    table.add_row("Trace ID:", trace.trace_id, "Status:", status_str)
    table.add_row("Run ID:", trace.run_id or "—", "Target ID:", trace.target_id or "—")
    table.add_row("Case ID:", trace.case_id or "—", "Wall Duration:", duration_str)
    table.add_row(
        "Total Spans:",
        str(len(trace.spans)),
        "Breakdown:",
        f"{llm_spans} LLM, {tool_spans} Tool, {ret_spans} Retrieval" + (f", [red]{err_spans} Error[/red]" if err_spans else ""),
    )

    return Panel(
        table,
        title=f"[bold cyan]Trace: {trace.name}[/bold cyan]",
        subtitle=f"[dim]schema v{trace.schema_version} • source: {trace.source}[/dim]",
        border_style="cyan",
        expand=False,
    )


def render_traces_table(traces: List[Trace]) -> Table:
    """Renders a tabular overview of traces."""
    table = Table(title="Canonical Traces", show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Trace ID", style="cyan", no_wrap=True)
    table.add_column("Case ID", style="white")
    table.add_column("Target", style="bold")
    table.add_column("Status", justify="center")
    table.add_column("Spans", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Created", style="dim")

    for t in traces:
        status_text = (
            "[green]OK[/green]"
            if t.status == SpanStatus.OK
            else (f"[red]{t.status.value.upper()}[/red]" if t.status == SpanStatus.ERROR else f"[yellow]{t.status.value.upper()}[/yellow]")
        )

        duration_str = "—"
        if t.start_time and t.end_time:
            duration_ms = (t.end_time - t.start_time).total_seconds() * 1000.0
            duration_str = f"{duration_ms:.1f}ms"
        elif t.spans:
            root_spans = t.get_root_spans()
            if root_spans and root_spans[0].duration_ms is not None:
                duration_str = f"{root_spans[0].duration_ms:.1f}ms"

        created_str = t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "—"

        table.add_row(
            t.trace_id,
            t.case_id or "—",
            t.target_id or "—",
            status_text,
            str(len(t.spans)),
            duration_str,
            created_str,
        )

    return table
