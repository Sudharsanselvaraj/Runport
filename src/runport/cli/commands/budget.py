"""Budget and spend governance CLI commands."""

from decimal import Decimal, InvalidOperation
import json
from datetime import datetime, timezone
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from runport.core.budget import BudgetService

console = Console()


def register_budget_commands(budget_app: typer.Typer) -> None:
    @budget_app.command(name="reconcile")
    def budget_reconcile(
        transaction_id: str = typer.Option(..., "--transaction-id", "-t", help="Unresolved ledger entry to resolve."),
        amount_usd: str = typer.Option(..., "--amount-usd", "-a", help="Real amount in USD read from the provider dashboard."),
        note: str = typer.Option("", "--note", help="Optional note, for example the dashboard date."),
    ) -> None:
        """Resolve an unresolved-spend entry with an amount you read from the provider dashboard. Live runs stay blocked until none remain."""
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
        console.print(
            f"Removed {result['ledger_rows']} simulated ledger rows, {result['runs']} dry-run runs and {result['results']} stored results.", markup=False
        )
        console.print(f"Backup of the previous database: {result['backup'] or 'none (no database file)'}", markup=False)

    @budget_app.command(name="audit")
    def budget_audit_cmd() -> None:
        """Reconcile the ledger with the stored results (read-only). Explains ledger total versus per-plan guard cost. Writes reports/budget_reconciliation_*.md/.json."""
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
        console.print(
            f"Ledger counted: ${a['ledger_total_counted_usd']}  remaining total ${a['remaining_usd']['total']}  pilot ceiling ${a['ceilings_usd']['pilot']}  unresolved {a['unresolved_entries']}",
            markup=False,
        )
        for g in a["groups"]:
            console.print(
                f"  {g['group']:<28}ledger ${g['ledger_usd']:<10} records ${g['records_recorded_cost_usd']:<10} guard ${g['guard_from_records_usd']:<10} ledger=records {g['ledger_equals_records']}",
                markup=False,
            )
        console.print(f"RECONCILED: {a['reconciled']}   report: {md.resolve()}", markup=False)
        raise typer.Exit(code=0 if a["reconciled"] else 1)

    @budget_app.command(name="policy")
    def budget_policy_cmd() -> None:
        """Show the effective ceilings and the audit trail of operator-authorized pilot-ceiling changes."""
        from runport.core import budget_policy as bp
        from runport.core.config import settings

        eff = bp.effective_policy(settings.budget, settings.data_dir)
        console.print(
            f"effective: total ${eff.total_budget_usd}  pilot ${eff.pilot_budget_usd}  per run ${eff.per_run_ceiling_usd}  per case ${eff.per_case_ceiling_usd}   (defaults: pilot ${settings.budget.pilot_budget_usd})",
            markup=False,
        )
        for h in bp.history(settings.data_dir):
            console.print(
                f"  {h['at']}  {h['operator']}: pilot ${h['previous_pilot_budget_usd']} -> ${h['new_pilot_budget_usd']}  (total ${h['total_budget_usd']}; ledger counted ${h['ledger_total_spent_usd']} at the time)",
                markup=False,
            )

    @budget_app.command(name="raise-pilot-ceiling")
    def budget_raise_pilot(
        to: str = typer.Option(..., "--to", help="New pilot ceiling in USD (never above the total lifetime ceiling)."),
        operator: str = typer.Option(..., "--operator", help="Your name, recorded in the audit trail."),
    ) -> None:
        """Operator-authorized pilot-ceiling change with an interactive typed phrase. The total, per-run and per-case ceilings and the ledger are untouched."""
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
            entry = bp.raise_pilot_ceiling(
                settings.data_dir,
                settings.budget,
                new,
                operator=operator,
                ledger_total_spent=st.cumulative_spend_usd,
                ledger_pilot_spent=st.pilot_spend_usd,
                echo=lambda line: console.print(line, markup=False, highlight=False),
            )
        except (LiveNotAuthorizedError, bp.PolicyError) as e:
            console.print(f"[bold red]Not changed:[/bold red] {e}")
            raise typer.Exit(code=1)
        console.print(
            f"Pilot ceiling is now ${entry['new_pilot_budget_usd']} (recorded in {bp.policy_path(settings.data_dir)}). Total ${entry['total_budget_usd']}, per-run ${entry['per_run_ceiling_usd']}, per-case ${entry['per_case_ceiling_usd']} unchanged.",
            markup=False,
        )

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
        if status.simulated_spend_usd > 0:
            console.print(f"[dim]Legacy simulated entries (never counted against any ceiling): ${status.simulated_spend_usd:.6f}[/dim]")
        if status.spend_by_basis:
            console.print("[dim]Booked spend by basis: " + ", ".join(f"{k} ${v:.6f}" for k, v in sorted(status.spend_by_basis.items())) + "[/dim]")
        if status.unresolved_spend_count:
            console.print(
                f"[bold red]UNRESOLVED SPEND: {status.unresolved_spend_count} request(s) have unknown cost. Live runs are blocked until you run "
                "`runport budget reconcile --transaction-id ... --amount-usd ...`.[/bold red]"
            )
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
                tx_type = (
                    "[yellow]PRE-RUN ESTIMATE[/yellow]"
                    if tx["is_preflight_estimate"]
                    else "[dim]LEGACY SIMULATED[/dim]"
                    if tx.get("is_simulated")
                    else "[bold red]UNRESOLVED[/bold red]"
                    if tx.get("is_unresolved")
                    else "[bold green]ACTUAL[/bold green]"
                    if basis in ("PROVIDER_REPORTED", "RECONCILED")
                    else "[yellow]ESTIMATED[/yellow]"
                    if basis == "ESTIMATED_FROM_CATALOG"
                    else f"[dim]{basis}[/dim]"
                )
                tx_table.add_row(
                    tx["timestamp"][:19].replace("T", " "),
                    tx["model_id"],
                    tx["provider"],
                    f"${Decimal(tx['amount_micros']) / Decimal('1000000'):.4f}",
                    tx_type,
                    tx["description"],
                )
            console.print(tx_table)
        else:
            console.print("[dim]No paid transactions recorded yet. Spend ledger is at baseline ($0.0000).[/dim]")
