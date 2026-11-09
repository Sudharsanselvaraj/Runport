"""Asynchronous job execution model and runner for Runport REST API v1.

Specification: docs/SDK_API_CONTRACT.md section 2.2 and Task 3.2.
Features:
- Non-blocking execution worker pool.
- Cooperative cancellation tokens stopping cleanly after the active case.
- Durable worker leases, atomic job claiming, and heartbeat renewals.
- Multi-process stale worker detection and crash recovery.
- Strictly executes via ExecutionService and GenericRunner (no bypass runner).
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import logging
import threading
from typing import Any, Dict, List, Optional
import uuid

from runport.api.v1.errors import NotFoundError
from runport.core.config import settings
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


class CooperativeCancelToken(threading.Event):
    """A cooperative cancellation token that simultaneously checks persistent database

    cancellation signals and extends worker lease heartbeats at each test case boundary.
    """

    def __init__(
        self,
        job_id: str,
        worker_id: str,
        db: DatabaseManager,
        in_memory_event: Optional[threading.Event] = None,
        lease_duration_s: int = 60,
    ):
        super().__init__()
        self.job_id = job_id
        self.worker_id = worker_id
        self.db = db
        self.in_memory_event = in_memory_event
        self.lease_duration_s = lease_duration_s
        self.lease_lost = False

    def is_set(self) -> bool:
        if super().is_set() or (self.in_memory_event and self.in_memory_event.is_set()):
            return True
        try:
            # Renew lease heartbeat before checking
            renewed = self.db.renew_job_lease(self.job_id, self.worker_id, self.lease_duration_s)
            if not renewed:
                # If renewal failed, check if job was cancelled or lease expired/lost
                job = self.db.get_run_job(self.job_id)
                if job and (job.get("cancelled") or str(job.get("status", "")).lower() == "cancelled"):
                    super().set()
                    if self.in_memory_event:
                        self.in_memory_event.set()
                    return True
                else:
                    self.lease_lost = True
                    super().set()
                    if self.in_memory_event:
                        self.in_memory_event.set()
                    return True
        except Exception:
            pass
        return False


class JobManager:
    """Manages asynchronous benchmark job queues, workers, leases, and cancellation."""

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

    def recover_interrupted_jobs(self, grace_period_s: int = 0) -> int:
        """Recovers jobs whose worker leases expired without heartbeat renewal.

        Reconciles orphaned states so jobs do not remain indefinitely stuck as active.
        Healthy workers actively executing with unexpired leases are never interrupted.
        """
        db = DatabaseManager(settings.db_path)
        db.init_db()
        try:
            recovered_ids = db.recover_stale_jobs(grace_period_s=grace_period_s)
            return len(recovered_ids)
        except Exception:
            logger.exception("Failed to recover stale run jobs during startup.")
            return 0

    def submit_job(
        self,
        plan_id: str,
        target_ids: List[str],
        dataset_path: str,
        sample_size: Optional[int] = None,
        requested_by: str = "api_v1",
        project_id: str = "default",
        requested_by_key_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Submits an approved plan for asynchronous execution."""
        db = DatabaseManager(settings.db_path)
        db.init_db()

        # Check existing idempotency key
        if idempotency_key:
            existing = db.get_run_job_by_idempotency_key(idempotency_key, project_id=project_id)
            if existing:
                return existing

        # Load cases to determine count
        cases = load_dataset_cases(dataset_path, sample_size)
        total_cases = len(cases)

        job_id = f"job-{uuid.uuid4().hex[:12]}"
        run_id = f"run-{uuid.uuid4().hex[:12]}"

        # Persist initial queued state with project ownership and optional idempotency key
        created_job = db.create_run_job(
            job_id=job_id,
            plan_id=plan_id,
            status="queued",
            total_cases=total_cases,
            run_id=run_id,
            project_id=project_id,
            requested_by_key_id=requested_by_key_id,
            idempotency_key=idempotency_key,
        )
        if created_job and created_job.get("job_id") != job_id:
            return created_job

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
        """Signals cooperative cancellation for a running or queued job across processes."""
        db = DatabaseManager(settings.db_path)
        db.init_db()

        # Signal in-memory worker if local
        with self._active_lock:
            ctx = self._active_jobs.get(job_id)
            if ctx:
                ctx.cancel_event.set()

        # Atomically update persistent database state
        job = db.request_job_cancellation(job_id, project_id=project_id)
        if not job:
            raise NotFoundError(f"Job '{job_id}' not found.")

        return job

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
        """Background thread executing the benchmark case by case with cancellation and lease checks."""
        db = DatabaseManager(settings.db_path)
        db.init_db()

        worker_id = f"worker-{uuid.uuid4().hex[:8]}"

        try:
            # Atomically claim the job established by submit_job
            claimed = db.claim_run_job(ctx.job_id, worker_id, lease_duration_s=60)
            if not claimed:
                # Another worker claimed it or it was cancelled while queued
                return

            cancel_token = CooperativeCancelToken(
                job_id=ctx.job_id,
                worker_id=worker_id,
                db=db,
                in_memory_event=ctx.cancel_event,
                lease_duration_s=60,
            )

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

            # Execute run through ExecutionService with cancellation and lease renewal token
            outcome = service.execute(
                plan_id=ctx.plan_id,
                targets=targets,
                specs=specs,
                cases=cases,
                cancel_token=cancel_token,
            )

            # Check if any run halted due to cancellation or lease loss
            was_cancelled = ctx.cancel_event.is_set() or cancel_token.is_set() or any(getattr(r, "halt_kind", None) == "cancelled" for r in outcome.runs)

            final_status = "interrupted" if cancel_token.lease_lost else ("cancelled" if was_cancelled else "completed")

            completed_cases = sum(r.successful_cases for r in outcome.runs)
            failed_cases = sum(r.failed_cases + r.invalid_cases for r in outcome.runs)
            spend_usd = sum((r.total_spend_usd for r in outcome.runs), Decimal("0.00"))

            # Record final status
            db.update_run_job(
                ctx.job_id,
                status=final_status,
                run_id=outcome.run_id,
                completed_cases=completed_cases,
                failed_cases=failed_cases,
                booked_spend_usd=f"{spend_usd:.6f}",
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
            db.release_run_reservations(run_id)
            with self._active_lock:
                self._active_jobs.pop(ctx.job_id, None)
