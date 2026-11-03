"""UI, Web, API Preflight, and welcome launcher CLI commands."""

import sys
import typer
from rich.console import Console
from rich.table import Table

console = Console()


def register_ui_commands(app: typer.Typer) -> None:
    @app.command("api-preflight")
    def api_preflight() -> None:
        """Report whether the API key is available WITHOUT showing it and WITHOUT sending any request."""
        import os
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
        from runport.cli.main import run_launcher_loop
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
