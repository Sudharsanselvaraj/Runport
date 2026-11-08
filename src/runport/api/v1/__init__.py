"""Runport Versioned REST API v1 Package.

Specification: docs/SDK_API_CONTRACT.md section 2.
"""

from fastapi import APIRouter

from runport.api.v1.routes import budget, datasets, plans, runs, targets, traces

api_v1_router = APIRouter(prefix="/v1")

api_v1_router.include_router(targets.router)
api_v1_router.include_router(datasets.router)
api_v1_router.include_router(plans.router)
api_v1_router.include_router(runs.router)
api_v1_router.include_router(budget.router)
api_v1_router.include_router(traces.router)

__all__ = ["api_v1_router"]
