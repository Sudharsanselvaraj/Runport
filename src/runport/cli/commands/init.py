"""Workspace initialization CLI command."""

from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel

from runport.core.workspace import init_workspace

console = Console()


def register_init_command(app: typer.Typer) -> None:
    @app.command("init")
    def init_cmd(
        directory: Path = typer.Option(Path.cwd(), "--dir", "-d", help="Directory in which to initialize workspace."),
        name: str = typer.Option("runport-workspace", "--name", "-n", help="Workspace name."),
        force: bool = typer.Option(False, "--force", "-f", help="Overwrite existing configuration file."),
    ) -> None:
        """Initialize a new Runport workspace configuration and directory tree."""
        try:
            cfg_path = init_workspace(directory, name=name, force=force)
            console.print(
                Panel(
                    f"[bold green]✓ Runport Workspace Initialized Successfully[/bold green]\n\n"
                    f"Configuration: [bold white]{cfg_path.resolve()}[/bold white]\n"
                    f"Evaluation:    [dim]{(directory / 'data' / 'evaluation').resolve()}[/dim]\n"
                    f"Reports:       [dim]{(directory / 'reports').resolve()}[/dim]\n\n"
                    f"[cyan]Default Ceilings:[/cyan] Total: $5.00 | Per-Run: $1.00 | Per-Case: $0.05 | Require Priced: False",
                    border_style="green",
                )
            )
        except FileExistsError as e:
            console.print(f"[bold red]Initialization Failed:[/bold red] {e}\n[dim]Use --force to overwrite existing runport.yaml.[/dim]")
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[bold red]Error initializing workspace:[/bold red] {e}")
            raise typer.Exit(code=1)
