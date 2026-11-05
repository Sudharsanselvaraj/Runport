"""Main CLI application assembly and interactive launcher loop."""

import sys
from typing import List
import typer
from rich.console import Console

console = Console()

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
    """Run a CLI command in-process exactly as if typed."""
    try:
        app(args=args, standalone_mode=False)
    except (SystemExit, typer.Exit):
        pass
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted.[/dim]")
    except Exception as e:
        console.print(f"[bold red]Command failed:[/bold red] {type(e).__name__}: {e}")


def handle_welcome_action(choice: int) -> None:
    """Dispatches one launcher choice to a real workflow."""
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
    """Show the launcher, run the chosen workflow, then come back to the menu."""
    from runport.tui.welcome import MENU_ITEMS, show_welcome_screen

    exit_choice = len(MENU_ITEMS)
    while True:
        choice = show_welcome_screen()
        handle_welcome_action(choice)
        if choice == exit_choice or choice == 0:
            break
        if choice != 1:
            try:
                console.input("\n[dim]Press Enter to return to the menu...[/dim]")
            except (EOFError, KeyboardInterrupt):
                break


def compute_sha256(filepath) -> str:
    """Computes SHA-256 hash of a file."""
    import hashlib

    sha256 = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            sha256.update(chunk)
    return sha256.hexdigest()


# Register commands from submodules
from runport.cli.commands.init import register_init_command
from runport.cli.commands.models import register_models_commands
from runport.cli.commands.budget import register_budget_commands
from runport.cli.commands.datasets import register_dataset_commands
from runport.cli.commands.traces import register_trace_commands
from runport.cli.commands.ui import register_ui_commands
from runport.cli.commands.benchmarks import register_benchmark_commands
from runport.cli.commands.plans import register_plan_commands

register_init_command(app)
register_models_commands(models_app)
register_budget_commands(budget_app)
register_dataset_commands(app)
register_trace_commands(app)
register_ui_commands(app)
register_benchmark_commands(app)
register_plan_commands(app)
