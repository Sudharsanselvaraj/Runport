"""Plan approval and the MCP server from the CLI."""

from typing import Optional
import typer
from rich.console import Console

console = Console()


def register_plan_commands(app: typer.Typer) -> None:
    @app.command("approve")
    def approve_cmd(plan_id: str = typer.Argument(..., help="Plan id, e.g. one an agent created over MCP.")) -> None:
        """Approve a pending live plan by typing its confirmation phrase (interactive terminals only)."""
        import getpass

        from runport.core.live_guard import confirm_live_run
        from runport.providers.base import LiveNotAuthorizedError
        from runport.services.execution import ExecutionService

        service = ExecutionService()
        plan = service.get_plan(plan_id)
        if plan is None:
            console.print(f"[bold red]No plan '{plan_id}'.[/bold red]")
            raise typer.Exit(code=1)
        projected = f"${plan.projected_max_cost_usd:.4f}" if plan.projected_max_cost_usd is not None else "unknown"
        lines = [
            f"Plan {plan.plan_id} requested by {plan.requested_by}: {plan.case_count} case(s) from {plan.dataset_label}.",
            f"Targets: {', '.join(plan.target_ids)}. Worst-case spend {projected}. Status {plan.status}.",
            *[f"  {t['target_id']} [{t.get('type')}, {t['billing']}]: {t['cost_note']}" for t in plan.per_target],
        ]
        for line in lines:
            console.print(line, markup=False)
        if plan.blockers:
            for b in plan.blockers:
                console.print(f"[bold red]Blocked:[/bold red] {b}")
            raise typer.Exit(code=1)
        try:
            confirm_live_run(plan.target_ids, [], plan_fingerprint=plan.fingerprint, echo=lambda line: console.print(line, markup=False, highlight=False))
            service.approve(plan.plan_id, plan.fingerprint, channel="cli_interactive", approver=getpass.getuser())
        except LiveNotAuthorizedError as e:
            console.print(f"[bold red]Not approved:[/bold red] {e}")
            raise typer.Exit(code=1)
        console.print(f"Approved {plan.plan_id}. It can be executed once within 15 minutes.", markup=False)

    mcp_app = typer.Typer(
        name="mcp",
        help="Runport as an MCP server for coding agents.",
        no_args_is_help=False,
    )

    @mcp_app.callback(invoke_without_command=True)
    def mcp_default(ctx: typer.Context) -> None:
        """Serve Runport's MCP tools over stdio by default."""
        if ctx.invoked_subcommand is None:
            from runport.mcp_server.server import RunportMcpServer

            RunportMcpServer().serve_stdio()

    @mcp_app.command("serve")
    def mcp_serve(
        transport: str = typer.Option(
            "stdio",
            "--transport",
            "-t",
            help="Transport mode: 'stdio' (default) or 'http' (Streamable HTTP / SSE).",
        ),
        host: str = typer.Option(
            "127.0.0.1",
            "--host",
            "-h",
            help="Host address for HTTP transport.",
        ),
        port: int = typer.Option(
            8000,
            "--port",
            "-p",
            help="Port number for HTTP transport.",
        ),
        token: Optional[str] = typer.Option(
            None,
            "--token",
            help="Optional Bearer token for authenticating HTTP connections.",
        ),
    ) -> None:
        """Serve Runport's MCP tools over stdio or Streamable HTTP. Agents can plan and inspect; only a person can approve spend."""
        from runport.mcp_server.server import RunportMcpServer

        server = RunportMcpServer()
        if transport.lower() == "stdio":
            server.serve_stdio()
        elif transport.lower() == "http":
            import uvicorn
            from fastapi import FastAPI
            from runport.mcp_server.http import create_mcp_router

            mcp_app = FastAPI(title="Runport MCP Server")
            mcp_app.include_router(create_mcp_router(server=server, auth_token=token), prefix="/mcp")
            console.print(f"[bold green]Starting Runport MCP Streamable HTTP server on http://{host}:{port}/mcp/sse ...[/bold green]")
            uvicorn.run(mcp_app, host=host, port=port, log_level="info")
        else:
            console.print(f"[bold red]Unsupported transport:[/bold red] {transport}. Use 'stdio' or 'http'.")
            raise typer.Exit(code=1)

    app.add_typer(mcp_app, name="mcp")
