"""Asynchronous job execution model and runner for Runport REST API v1.

Specification: docs/SDK_API_CONTRACT.md section 2.2 and Task 3.2.
Features:
- Non-blocking execution worker pool.
- Cooperative cancellation tokens stopping cleanly after the active case.
- In-memory active registry + SQLite persistence for state across restarts.
- Strictly executes via ExecutionService and GenericRunner (no bypass runner).
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional
import uuid

from runport.api.v1.errors import NotFoundError, PlanBlockedError
from runport.connectors.registry import TargetSpecError
from runport.core.config import settings
from runport.runs.executor import GenericRunner
from runport.services.execution import ExecutionService, load_dataset_cases
from runport.storage.db import DatabaseManager

logger = logging.getLogger(__name__)


class JobContext:
    """In-memory active execution context for a job."""

    def __init__(self, job_id: str, plan_id: str):
        self.job_id = job_id
        self.plan_id = plan_id
        self.cancel_event = threading.Event()
        self.thread: Optional[threading.Thread] = None


class JobManager:
    """Manages asynchronous benchmark job queues, workers, and cancellation."""

    _instance: Optional[JobManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> JobManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._active_jobs: Dict[str, JobContext] = {}
                cls._instance._active_lock = threading.Lock()
                cls._instance.recover_interrupted_jobs()
            return cls._instance

    def recover_interrupted_jobs(self) -> int:
        """Recovers jobs that were interrupted in 'queued' or 'running' state by a process restart.

        Reconciles orphaned states so jobs do not remain indefinitely stuck as active.
        """
        db = DatabaseManager(settings.db_path)
        db.init_db()
        interrupted = 0
        now = datetime.now(timezone.utc).isoformat()
        try:
            for job in db.list_run_jobs(limit=500):
                if str(job.get("status", "")).lower() in ("queued", "running"):
                    is_cancelled = bool(job.get("cancelled"))
                    new_status = "cancelled" if is_cancelled else "failed"
                    err = None if is_cancelled else "Execution interrupted by process shutdown or restart."
                    db.update_run_job(
                        job["job_id"],
                        status=new_status,
                        cancelled=is_cancelled,
                        error_message=err,
                        finished_at=now,
                    )
                    interrupted += 1
        except Exception:
            logger.exception("Failed to recover interrupted run jobs during startup.")
        return interrupted

    def submit_job(
        self,
        plan_id: str,
        target_ids: List[str],
        dataset_path: str,
        sample_size: Optional[int] = None,
        requested_by: str = "api_v1",
        project_id: str = "default",
        requested_by_key_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submits an approved plan for asynchronous execution."""
        db = DatabaseManager(settings.db_path)
        db.init_db()

        # Load cases to determine count
        cases = load_dataset_cases(dataset_path, sample_size)
        total_cases = len(cases)

        job_id = f"job-{uuid.uuid4().hex[:12]}"
        run_id = f"run-{uuid.uuid4().hex[:12]}"

        # Persist initial queued state with project ownership
        db.create_run_job(
            job_id=job_id,
            plan_id=plan_id,
            status="queued",
            total_cases=total_cases,
            run_id=run_id,
            project_id=project_id,
            requested_by_key_id=requested_by_key_id,
        )

        ctx = JobContext(job_id=job_id, plan_id=plan_id)
        with self._active_lock:
            self._active_jobs[job_id] = ctx

        # Start execution thread
        worker = threading.Thread(
            target=self._run_job_worker,
            args=(ctx, run_id, target_ids, dataset_path, sample_size),
            daemon=True,
            name=f"job-worker-{job_id}",
        )
        ctx.thread = worker
        worker.start()

        return db.get_run_job(job_id, project_id=project_id) or {}

    def cancel_job(self, job_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Signals cooperative cancellation for a running or queued job, scoped by project."""
        db = DatabaseManager(settings.db_path)
        db.init_db()

        job = db.get_run_job(job_id, project_id=project_id)
        if not job:
            raise NotFoundError(f"Job '{job_id}' not found.")

        # Signal in-memory worker
        with self._active_lock:
            ctx = self._active_jobs.get(job_id)
            if ctx:
                ctx.cancel_event.set()

        # Update database status
        if str(job.get("status", "")).lower() in ("queued", "running"):
            db.update_run_job(
                job_id,
                cancelled=True,
                status="cancelled",
                finished_at=datetime.now(timezone.utc).isoformat(),
            )

        return db.get_run_job(job_id, project_id=project_id) or {}

    def get_job(self, job_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves current job status and progress, scoped by project."""
        db = DatabaseManager(settings.db_path)
        db.init_db()

        job = db.get_run_job(job_id, project_id=project_id)
        if not job:
            raise NotFoundError(f"Job '{job_id}' not found.")
        return job

    def list_jobs(self, limit: int = 50, project_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists recent benchmark execution jobs, optionally filtered by project_id."""
        db = DatabaseManager(settings.db_path)
        db.init_db()
        return db.list_run_jobs(limit=limit, project_id=project_id)

    def _run_job_worker(
        self,
        ctx: JobContext,
        run_id: str,
        target_ids: List[str],
        dataset_path: str,
        sample_size: Optional[int],
    ) -> None:
        """Background thread executing the benchmark case by case with cancellation checks."""
        db = DatabaseManager(settings.db_path)
        db.init_db()

        try:
            # Check early cancellation from in-memory token or persistent database state
            persisted = db.get_run_job(ctx.job_id)
            if ctx.cancel_event.is_set() or (persisted and (persisted.get("cancelled") or persisted.get("status") == "cancelled")):
                ctx.cancel_event.set()
                db.update_run_job(
                    ctx.job_id,
                    status="cancelled",
                    cancelled=True,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                return

            db.update_run_job(ctx.job_id, status="running")

            service = ExecutionService()
            plan = service.get_plan(ctx.plan_id)
            if not plan:
                db.update_run_job(
                    ctx.job_id,
                    status="failed",
                    error_message=f"Plan '{ctx.plan_id}' no longer exists.",
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                return

            targets, specs = service.resolve(target_ids)
            cases = load_dataset_cases(dataset_path, sample_size)

            # Execute run through ExecutionService with cancellation token
            outcome = service.execute(
                plan_id=ctx.plan_id,
                targets=targets,
                specs=specs,
                cases=cases,
                cancel_token=ctx.cancel_event,
            )

            # Check if any run halted due to cancellation
            was_cancelled = ctx.cancel_event.is_set() or any(getattr(r, "halt_kind", None) == "cancelled" for r in outcome.runs)

            # Record final status
            db.update_run_job(
                ctx.job_id,
                status="cancelled" if was_cancelled else "completed",
                run_id=outcome.run_id,
                completed_cases=len(outcome.results),
                failed_cases=sum(1 for r in outcome.results if r.is_error),
                booked_spend_usd=str(outcome.spend) if outcome.spend is not None else "0.0000",
                finished_at=datetime.now(timezone.utc).isoformat(),
                cancelled=was_cancelled,
            )

        except Exception as e:
            logger.exception("Error executing asynchronous job %s", ctx.job_id)
            db.update_run_job(
                ctx.job_id,
                status="failed",
                error_message=str(e),
                finished_at=datetime.now(timezone.utc).isoformat(),
            )
        finally:
            with self._active_lock:
                self._active_jobs.pop(ctx.job_id, None)
