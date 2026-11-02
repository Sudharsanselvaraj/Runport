"""FastAPI application factory for the Runport web dashboard and REST API."""

import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from runport.api.routes import budget, datasets, events, plan, runs, targets


def create_app() -> FastAPI:
    """Creates and configures the Runport FastAPI application."""
    app = FastAPI(
        title="Runport",
        description="Universal LLM, Prompt, and Workflow Benchmarking Platform",
        version="0.1.0",
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

    # API routers
    app.include_router(targets.router, prefix="/api")
    app.include_router(datasets.router, prefix="/api")
    app.include_router(budget.router, prefix="/api")
    app.include_router(plan.router, prefix="/api")
    app.include_router(runs.router, prefix="/api")
    app.include_router(events.router, prefix="/api")

    @app.get("/api/health")
    def health_check():
        return {
            "status": "ok",
            "app": "runport",
            "version": "0.1.0",
            "mode": "local_first",
        }

    # Serve static assets if the Vite build is present in web/dist
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    frontend_dist = repo_root / "web" / "dist"

    if frontend_dist.exists() and (frontend_dist / "index.html").exists():
        app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")
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

