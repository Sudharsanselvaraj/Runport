"""FastAPI application factory for the Runport web dashboard and REST API."""

import hmac
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from runport import __version__
from runport.api.routes import budget, datasets, events, models, plan, reports, runs, setup, targets, traces
from runport.api.v1 import api_v1_router
from runport.api.v1.errors import ApiV1Error
from runport.mcp_server.http import create_mcp_router


_PUBLIC_API_PATHS = frozenset({"/api/health", "/api/docs", "/api/openapi.json", "/api/redoc"})
_LOOPBACK_CLIENTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})  # "testclient" is Starlette's in-process TestClient
_LOOPBACK_HOST_NAMES = frozenset({"localhost", "127.0.0.1", "::1", "[::1]"})


def _host_name(host_header: str) -> str:
    host = host_header.strip().lower()
    if host.startswith("["):  # [::1]:8000
        return host.split("]")[0] + "]"
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def _access_policy_middleware(api_token: Optional[str], extra_allowed_hosts: str):
    """Access policy for /api routes (static dashboard files are not gated).

    * Token configured (RUNPORT_API_TOKEN): every /api request, local or remote, must present exactly that token
      as `Authorization: Bearer <token>` or `X-Runport-Token`. Compared in constant time.
    * No token configured (local development): only loopback clients are served, and only when the Host header is a
      loopback name (or listed in RUNPORT_ALLOWED_HOSTS), which blocks DNS-rebinding from a browser. Remote clients
      are refused outright, whatever credentials they send: remote access fails closed until a token is set.
    """
    allowed_hosts = _LOOPBACK_HOST_NAMES | {h.strip().lower() for h in extra_allowed_hosts.split(",") if h.strip()}

    async def middleware(request: Request, call_next):
        path = request.url.path
        if not path.startswith("/api") or path in _PUBLIC_API_PATHS:
            return await call_next(request)

        if api_token:
            auth_header = request.headers.get("Authorization", "")
            presented = auth_header[7:].strip() if auth_header.startswith("Bearer ") else request.headers.get("X-Runport-Token", "")
            if not presented or not hmac.compare_digest(presented.encode("utf-8"), api_token.encode("utf-8")):
                return JSONResponse(status_code=401, content={"detail": "Unauthorized: a valid RUNPORT_API_TOKEN is required."})
            return await call_next(request)

        client_host = request.client.host if request.client else ""
        if client_host not in _LOOPBACK_CLIENTS:
            return JSONResponse(
                status_code=403,
                content={"detail": "Remote access is disabled. Set RUNPORT_API_TOKEN on the server to allow authenticated network access."},
            )
        if _host_name(request.headers.get("host", "")) not in allowed_hosts:
            return JSONResponse(status_code=403, content={"detail": "Host header is not a loopback name; request refused (DNS-rebinding protection)."})
        return await call_next(request)

    return middleware


def create_app() -> FastAPI:
    """Creates and configures the Runport FastAPI application."""
    app = FastAPI(
        title="Runport",
        description="Universal LLM, Prompt, and Workflow Benchmarking Platform",
        version=__version__,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Strict local-first CORS policy
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.middleware("http")(_access_policy_middleware(os.environ.get("RUNPORT_API_TOKEN") or None, os.environ.get("RUNPORT_ALLOWED_HOSTS", "")))

    # API routers
    app.include_router(setup.router, prefix="/api")
    app.include_router(models.router, prefix="/api")
    app.include_router(targets.router, prefix="/api")
    app.include_router(datasets.router, prefix="/api")
    app.include_router(budget.router, prefix="/api")
    app.include_router(plan.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(reports.router, prefix="/api")
    app.include_router(events.router, prefix="/api")
    app.include_router(traces.router, prefix="/api")

    # Versioned REST API v1
    app.include_router(api_v1_router, prefix="/api")

    # MCP Streamable HTTP (SSE) Transport
    app.include_router(create_mcp_router(path_prefix="/mcp"), prefix="/mcp")

    @app.exception_handler(ApiV1Error)
    async def api_v1_error_handler(request: Request, exc: ApiV1Error):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.error_message, "details": exc.details}},
        )

    @app.get("/api/health")
    def health_check():
        return {
            "status": "ok",
            "app": "runport",
            "version": __version__,
            "mode": "local_first",
        }

    # Serve packaged UI from src/runport/_web or dev build from web/dist
    packaged_web = Path(__file__).resolve().parent.parent / "_web"
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    dev_dist = repo_root / "web" / "dist"

    dist_dir = packaged_web if (packaged_web / "index.html").exists() else dev_dist
    if dist_dir.exists() and (dist_dir / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
    else:

        @app.get("/", response_class=HTMLResponse)
        def index_fallback():
            return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Runport Benchmarking Platform</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #0c1017; color: #e6edf3; padding: 2rem; margin: 0; }
        .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 1.5rem; max-width: 800px; margin: 2rem auto; }
        h1 { color: #58a6ff; margin-top: 0; }
        a { color: #79c0ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        .badge { display: inline-block; padding: 0.2rem 0.5rem; background: #1f2937; border-radius: 4px; font-size: 0.85rem; }
        pre { background: #0d1117; padding: 1rem; border-radius: 6px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="card">
        <h1>Runport Benchmarking Platform</h1>
        <p>Local-first, fail-closed LLM and workflow evaluation platform.</p>
        <p><span class="badge">API Status: Running</span> | <a href="/api/docs">Interactive API Documentation (Swagger)</a></p>
        <hr style="border: 0; border-top: 1px solid #30363d; margin: 1.5rem 0;">
        <h3>Available API Endpoints:</h3>
        <ul>
            <li><code>GET /api/health</code> - Service health & status</li>
            <li><code>GET /api/targets</code> - Catalog models and custom workflow connectors</li>
            <li><code>GET /api/datasets</code> - Evaluation datasets</li>
            <li><code>GET /api/budget</code> - Spend ledger and remaining caps</li>
            <li><code>POST /api/plan</code> - Honest costed plan & cryptographic fingerprint</li>
            <li><code>POST /api/runs</code> - Live or Replayed evaluation execution</li>
            <li><code>GET /api/events</code> - Live SSE telemetry event stream</li>
        </ul>
    </div>
</body>
</html>"""

    return app
