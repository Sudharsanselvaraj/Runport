"""Model catalog CLI commands."""

import typer
from rich.console import Console
from rich.table import Table

from runport.models.catalog import get_portfolio

console = Console()


def register_models_commands(models_app: typer.Typer) -> None:
    @models_app.command("roster")
    def models_roster() -> None:
        """Show registered model portfolio candidates and their attributes."""
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

    @models_app.command(name="list")
    def models_list() -> None:
        """List the comparison participants (same view as `models roster`)."""
        models_roster()
