"""Main CLI application assembly and interactive launcher loop."""

import sys
from typing import List, Optional
import typer
from rich.console import Console

# Gracefully handle console encodings on legacy Windows consoles without UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass

console = Console()


def version_callback(value: bool) -> None:
    if value:
        from runport import __version__

        console.print(f"runport {__version__}")
        raise typer.Exit()


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
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show Runport version and exit.",
        callback=version_callback,
        is_eager=True,
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
    """Dispatches one launcher choice to its corresponding functional onboarding workflow."""
    from runport.tui.onboarding import OnboardingEngine

    engine = OnboardingEngine(console=console)

    if choice == 1:
        # (A) Explore a benchmark workspace
        engine.explore_workspace()
    elif choice == 2:
        # (B) Run a model benchmark
        engine.run_benchmark_flow()
    elif choice == 3:
        # (C) Evaluate a dataset
        engine.evaluate_dataset_flow()
    elif choice == 4:
        # (D) Compare models and inspect results
        engine.compare_results_flow()
    elif choice == 5:
        # (E) Open the interactive dashboard
        from runport.tui.app import run_tui

        run_tui()
    elif choice in (6, 8):
        # (F) Configure providers and settings (8 is legacy alias)
        engine.configure_providers_flow()
    elif choice in (7, 9):
        # (G) Skip onboarding and open the shell (9 is legacy alias)
        engine.skip_and_exit()


def run_launcher_loop() -> None:
    """Show the launcher, run the chosen workflow, then come back to the menu."""
    from runport.tui.welcome import MENU_ITEMS, show_welcome_screen

    exit_choice = len(MENU_ITEMS)
    while True:
        choice = show_welcome_screen()
        handle_welcome_action(choice)
        if choice in (exit_choice, 0, 7, 9):
            break
        if choice != 5:  # Dashboard handles its own session and returns cleanly
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
