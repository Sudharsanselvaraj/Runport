"""Runport Remote Python Client.

Specification: docs/SDK_API_CONTRACT.md section 3.
Provides high-level programmatic access to Runport's REST API v1.
"""

import time
from typing import Any, Dict, List, Optional
import httpx

from runport.client.errors import ClientError, raise_for_api_error
from runport.client.models import (
    BudgetStatus,
    DatasetItem,
    Job,
    Plan,
    Result,
    Run,
    TargetItem,
)


class Client:
    """Remote Python Client for Runport REST API v1.

    Args:
        base_url: Base URL of the Runport daemon (default: http://127.0.0.1:8000).
        api_key: Optional bearer API key with required operation scopes.
        timeout: Request timeout in seconds.
        transport: Optional custom httpx transport (e.g. for offline mock testing).
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8000",
        api_key: Optional[str] = None,
        timeout: float = 30.0,
        transport: Optional[httpx.BaseTransport] = None,
        http_client: Optional[Any] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

        if http_client is not None:
            self._client = http_client
        else:
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            self._client = httpx.Client(
                base_url=self.base_url,
                headers=headers,
                timeout=timeout,
                transport=transport,
            )

    def close(self) -> None:
        """Closes the underlying HTTP client session."""
        self._client.close()

    def __enter__(self) -> "Client":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[Any] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """Performs HTTP request with automatic error envelope parsing."""
        url = f"/api/v1{path}"
        try:
            resp = self._client.request(method, url, json=json, params=params)
        except httpx.RequestError as e:
            raise ClientError("network_error", f"Failed to connect to Runport at {self.base_url}: {e}", 503) from e

        if resp.is_success:
            return resp.json()

        try:
            data = resp.json()
            if isinstance(data, dict) and "error" in data:
                raise_for_api_error(resp.status_code, data["error"])
        except ValueError:
            pass

        resp.raise_for_status()

    # =========================================================================
    # Targets
    # =========================================================================

    def list_targets(self) -> List[TargetItem]:
        """Lists available benchmark targets across catalog models and connectors."""
        data = self._request("GET", "/targets")
        return [TargetItem(**item) for item in data]

    def get_target(self, target_id: str) -> TargetItem:
        """Retrieves details of a specific target by ID."""
        data = self._request("GET", f"/targets/{target_id}")
        return TargetItem(**data)

    # =========================================================================
    # Datasets
    # =========================================================================

    def list_datasets(self) -> List[DatasetItem]:
        """Lists all evaluation datasets in the workspace."""
        data = self._request("GET", "/datasets")
        return [DatasetItem(**item) for item in data]

    def upload_dataset(self, name: str, cases: List[Dict[str, Any]]) -> DatasetItem:
        """Uploads and registers an evaluation dataset (validated and hashed)."""
        import json
        content_lines = "\n".join(json.dumps(c) for c in cases) + "\n"
        files = {"file": (name, content_lines.encode("utf-8"), "application/json")}
        resp = self._client.post(f"{self.base_url}/api/v1/datasets", files=files)
        if not resp.is_success:
            try:
                data = resp.json()
                if isinstance(data, dict) and "error" in data:
                    raise_for_api_error(resp.status_code, data["error"])
            except Exception:
                pass
            resp.raise_for_status()
        return DatasetItem(**resp.json())

    # =========================================================================
    # Plans & Approvals
    # =========================================================================

    def plan(
        self,
        target_ids: List[str],
        dataset: str,
        sample_size: Optional[int] = None,
        is_pilot: bool = False,
    ) -> Plan:
        """Creates a costed, fingerprinted benchmark execution plan.

        Sends no live requests. Plan remains PENDING until approved.
        """
        payload = {
            "target_ids": target_ids,
            "dataset_name": dataset,
            "sample_size": sample_size,
            "is_pilot": is_pilot,
        }
        data = self._request("POST", "/plans", json=payload)
        return Plan(**data)

    def get_plan(self, plan_id: str) -> Plan:
        """Retrieves an execution plan by its ID."""
        data = self._request("GET", f"/plans/{plan_id}")
        return Plan(**data)

    def approve(self, plan_id: str, fingerprint: str, approver: str = "operator") -> Plan:
        """Human operator approves a PENDING plan using its cryptographic fingerprint."""
        payload = {"fingerprint": fingerprint, "approver": approver}
        data = self._request("POST", f"/plans/{plan_id}/approve", json=payload)
        return Plan(**data)

    # =========================================================================
    # Run Jobs Execution
    # =========================================================================

    def execute(
        self,
        plan_id: str,
        sample_size: Optional[int] = None,
        idempotency_key: Optional[str] = None,
    ) -> Job:
        """Submits an approved plan for asynchronous background execution."""
        payload = {"sample_size": sample_size, "idempotency_key": idempotency_key}
        data = self._request("POST", f"/plans/{plan_id}/runs", json=payload)
        return Job(**data)

    def get_job(self, job_id: str) -> Job:
        """Retrieves progress and status of an execution job."""
        data = self._request("GET", f"/jobs/{job_id}")
        return Job(**data)

    def cancel_job(self, job_id: str) -> Job:
        """Cooperatively cancels an active or queued execution job."""
        data = self._request("POST", f"/jobs/{job_id}/cancel")
        return Job(**data)

    def wait(
        self,
        job_id: str,
        timeout_s: float = 300.0,
        poll_interval_s: float = 0.5,
    ) -> Job:
        """Blocks until a job completes, fails, or is cancelled, or until timeout."""
        start = time.time()
        while True:
            job = self.get_job(job_id)
            if job.is_finished:
                return job
            if time.time() - start > timeout_s:
                raise TimeoutError(f"Job '{job_id}' timed out after {timeout_s}s.")
            time.sleep(poll_interval_s)

    # =========================================================================
    # Runs, Results & Traces
    # =========================================================================

    def get_run(self, run_id: str) -> Run:
        """Retrieves completed evaluation run metadata."""
        data = self._request("GET", f"/runs/{run_id}")
        return Run(**data)

    def list_runs(self, limit: int = 50) -> List[Run]:
        """Lists recent benchmark execution runs."""
        data = self._request("GET", "/runs", params={"limit": limit})
        return [Run(**item) for item in data]

    def get_results(self, run_id: str, limit: int = 100, offset: int = 0) -> List[Result]:
        """Retrieves case execution results for an evaluation run."""
        data = self._request("GET", f"/runs/{run_id}/results", params={"limit": limit, "offset": offset})
        return [Result(**item) for item in data]

    def get_trace(self, case_id: str, run_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves canonical trace for an evaluation case."""
        params = {"run_id": run_id} if run_id else None
        return self._request("GET", f"/traces/{case_id}", params=params)

    def submit_trace(self, trace_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submits an OTLP or canonical trace for telemetry ingestion."""
        return self._request("POST", "/traces", json=trace_payload)

    # =========================================================================
    # Budget
    # =========================================================================

    def get_budget(self) -> BudgetStatus:
        """Retrieves budget limits, spend breakdown, and unresolved ledger status."""
        data = self._request("GET", "/budget")
        return BudgetStatus(**data)
