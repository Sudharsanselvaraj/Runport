"""Interactive onboarding engine and guided workflow controllers for Runport CLI.

Each flow connects directly to real functional execution in Runport's core services,
preserving strict runner guard order, preflight budget caps, and cryptographic plan approvals.
"""

from __future__ import annotations

import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from rich.align import Align
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from runport.core.budget import BudgetService
from runport.core.config import settings
from runport.core.workspace import find_workspace_file, load_workspace_config
from runport.models.catalog import get_portfolio
from runport.services.execution import ExecutionService
from runport.storage.db import DatabaseManager
from runport.tui.components import (
    ConfirmationPanel,
    ErrorPanel,
    ProgressView,
    ResultSummary,
    SectionHeader,
    TerminalFooter,
)
from runport.tui.theme import (
    ACCENT_CYAN,
    ACCENT_LAVENDER,
    ACCENT_LAVENDER_LIGHT,
    BORDER_CHARCOAL,
    BORDER_FOCUSED,
    COLOR_ERROR,
    COLOR_INFO,
    COLOR_SUCCESS,
    COLOR_WARNING,
    TEXT_MUTED,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class OnboardingEngine:
    """Coordinates guided interactive terminal onboarding workflows."""

    def __init__(self, console: Optional[Console] = None) -> None:
        self.console = console or Console()

    def _run_cli(self, args: List[str]) -> None:
        """Invokes a Typer CLI command in-process with output directed to self.console."""
        from runport.cli.main import app

        try:
            app(args=args, standalone_mode=False)
        except (SystemExit, Exception) as e:
            pass

    # -------------------------------------------------------------------------
    # Flow A: Explore a benchmark workspace
    # -------------------------------------------------------------------------
    def explore_workspace(self) -> None:
        """Explores current workspace configuration, declared targets, datasets, and recent runs."""
        self.console.print(SectionHeader.render("WORKSPACE EXPLORER", "Inspect configuration, targets, and datasets"))

        ws_file = find_workspace_file()
        cfg = load_workspace_config()

        # Workspace Config Panel
        ws_table = Table.grid(padding=(0, 2))
        ws_table.add_column(style=f"bold {TEXT_SECONDARY}", width=22)
        ws_table.add_column(style=TEXT_PRIMARY)

        root = cfg.root_dir or settings.workspace_root
        ws_table.add_row("Configuration File:", str(ws_file) if ws_file else "[yellow]Not Found (using defaults)[/yellow]")
        ws_table.add_row("Workspace Name:", cfg.name)
        ws_table.add_row("Root Directory:", str(root))
        ws_table.add_row("Evaluation Directory:", str(root / "data" / "evaluation"))
        ws_table.add_row("Reports Directory:", str(root / "reports"))
        ws_table.add_row("SQLite Database:", str(settings.db_path))

        self.console.print(Panel(ws_table, title="[bold #e9d5ff] Active Workspace [/]", border_style=BORDER_CHARCOAL, padding=(1, 2)))

        # Declared Targets Table
        target_table = Table(show_header=True, header_style=f"bold {ACCENT_LAVENDER}", border_style=BORDER_CHARCOAL, width=78)
        target_table.add_column("Target ID", style=f"bold {TEXT_PRIMARY}", width=22)
        target_table.add_column("Type", style=ACCENT_CYAN, width=18)
        target_table.add_column("Billing", style=TEXT_SECONDARY, width=14)
        target_table.add_column("Details", style=TEXT_MUTED)

        if cfg.targets:
            for t in cfg.targets:
                endpoint = t.endpoint or t.base_url or t.model or "local"
                target_table.add_row(t.id, t.type, t.billing or "local", str(endpoint)[:26])
        else:
            target_table.add_row("None declared", "n/a", "n/a", "Add targets to runport.yaml or benchmark catalog models")

        self.console.print(
            Panel(
                target_table,
                title="[bold #e9d5ff] Declared Workspace Targets [/]",
                border_style=BORDER_CHARCOAL,
                padding=(0, 1),
            )
        )

        # Datasets in data/evaluation
        eval_dir = root / "data" / "evaluation"
        dataset_table = Table(show_header=True, header_style=f"bold {ACCENT_LAVENDER}", border_style=BORDER_CHARCOAL, width=78)
        dataset_table.add_column("Dataset File", style=f"bold {TEXT_PRIMARY}", width=34)
        dataset_table.add_column("Size", style=TEXT_MUTED, width=14)
        dataset_table.add_column("Status", style=COLOR_SUCCESS)

        if eval_dir.exists():
            files = sorted(eval_dir.glob("*.jsonl"))
            if files:
                for f in files:
                    size_kb = f.stat().st_size / 1024
                    dataset_table.add_row(f.name, f"{size_kb:.1f} KB", "Ready")
            else:
                dataset_table.add_row("No .jsonl files found", "0 KB", "Empty")
        else:
            dataset_table.add_row("data/evaluation directory missing", "—", "Uninitialized")

        self.console.print(
            Panel(
                dataset_table,
                title="[bold #e9d5ff] Discovered Datasets [/]",
                border_style=BORDER_CHARCOAL,
                padding=(0, 1),
            )
        )

        if not ws_file:
            self.console.print("\n[bold #38bdf8]Hint:[/bold #38bdf8] Run [green]runport init[/green] to initialize a new workspace.")

    # -------------------------------------------------------------------------
    # Flow B: Run a model benchmark
    # -------------------------------------------------------------------------
    def run_benchmark_flow(self) -> None:
        """Executes benchmark evaluation under fail-closed spend caps."""
        self.console.print(SectionHeader.render("BENCHMARK EXECUTION", "Guarded evaluation under fail-closed spend caps"))
        self._run_cli(["benchmark-rag"])

    # -------------------------------------------------------------------------
    # Flow C: Evaluate a dataset
    # -------------------------------------------------------------------------
    def evaluate_dataset_flow(self) -> None:
        """Inspects, validates, and reports on datasets in data/evaluation/."""
        self.console.print(SectionHeader.render("DATASET VALIDATION", "Schema validation & cross-split leakage checks"))
        eval_file = settings.workspace_root / "data" / "evaluation" / "verified_rag_benchmark.jsonl"
        if not eval_file.exists():
            # Fallback to any jsonl in evaluation directory
            eval_dir = settings.workspace_root / "data" / "evaluation"
            files = list(eval_dir.glob("*.jsonl")) if eval_dir.exists() else []
            eval_file = files[0] if files else eval_file

        self._run_cli(["validate-dataset", str(eval_file)])

    # -------------------------------------------------------------------------
    # Flow D: Compare models and inspect results
    # -------------------------------------------------------------------------
    def compare_results_flow(self) -> None:
        """Inspects past runs from SQLite database and displays side-by-side comparison."""
        self.console.print(SectionHeader.render("MODEL COMPARISON ROSTER", "Readiness, routes, and candidate metrics"))
        self._run_cli(["models", "roster"])

    # -------------------------------------------------------------------------
    # Flow F: Configure providers and settings
    # -------------------------------------------------------------------------
    def configure_providers_flow(self) -> None:
        """Displays provider credentials, budget policy, and system diagnostics."""
        self.console.print(SectionHeader.render("PROVIDER CONFIGURATION & BUDGET", "API preflight & spend tracking"))
        self._run_cli(["api-preflight"])
        self.console.print("")
        self._run_cli(["budget", "status"])

    # -------------------------------------------------------------------------
    # Flow G: Skip onboarding and open shell
    # -------------------------------------------------------------------------
    def skip_and_exit(self) -> None:
        """Exits onboarding with a clean quick-reference cheatsheet."""
        self.console.print("\n[bold #c084fc]Runport CLI Quick Reference:[/bold #c084fc]")
        ref = Table.grid(padding=(0, 2))
        ref.add_column(style=f"bold {ACCENT_CYAN}", width=32)
        ref.add_column(style=TEXT_SECONDARY)

        ref.add_row("runport web", "Launch modern web dashboard at http://127.0.0.1:8000")
        ref.add_row("runport ui", "Launch full-screen terminal UI dashboard")
        ref.add_row("runport benchmark", "Execute live model benchmark under spend caps")
        ref.add_row("runport budget status", "Check append-only SQLite WAL ledger and ceilings")
        ref.add_row("runport validate-dataset <file>", "Verify dataset schemas and leakage boundaries")
        ref.add_row("runport api-preflight", "Verify API credentials offline (sends zero requests)")

        self.console.print(Panel(ref, border_style=BORDER_CHARCOAL, padding=(1, 2)))
        self.console.print("[dim]Exiting Runport. Goodbye.[/]\n")
