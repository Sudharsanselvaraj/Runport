"""Python callable and subprocess execution targets for Runport.

Allows benchmarking in-memory Python pipelines, functions, and standalone CLI binaries.
"""

import importlib
import json
import subprocess
import time
from typing import Any, Callable, Dict, List, Optional, Union

from runport.providers.base import scrub_secrets
from runport.targets.base import (
    BillingMode,
    CostBasis,
    Target,
    TargetPricing,
    TargetResult,
    TargetStatus,
    TargetType,
)


class PythonCallableTarget(Target):
    """Benchmarks a local Python callable in-process."""

    def __init__(
        self,
        target_id: str,
        name: str,
        func: Union[Callable[[Dict[str, Any]], Any], str],
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(
            target_id=target_id,
            name=name,
            target_type=TargetType.PYTHON_CALLABLE,
            capabilities=["python", "in_process"],
            pricing=pricing,
            timeout_seconds=timeout_seconds,
            max_retries=1,
            billing=BillingMode.LOCAL,
        )
        if isinstance(func, str):
            module_name, func_name = func.split(":")
            mod = importlib.import_module(module_name)
            self._callable = getattr(mod, func_name)
        else:
            self._callable = func

    def execute(
        self,
        input_payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> TargetResult:
        start_time = time.perf_counter()
        try:
            raw_output = self._callable(input_payload)
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            if isinstance(raw_output, TargetResult):
                if raw_output.latency_ms is None:
                    raw_output.latency_ms = elapsed_ms
                return raw_output

            if isinstance(raw_output, dict):
                output_text = raw_output.get("output") or raw_output.get("answer") or json.dumps(raw_output)
            else:
                output_text = str(raw_output)

            cost_usd = None
            cost_basis = CostBasis.UNAVAILABLE
            if self.pricing:
                cost_usd = self.pricing.calculate_cost(None, None)
                if cost_usd is not None:
                    cost_basis = CostBasis.ESTIMATED

            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.SUCCESS,
                output_text=output_text,
                raw_output=scrub_secrets(raw_output) if isinstance(raw_output, (dict, list)) else raw_output,
                latency_ms=elapsed_ms,
                cost_usd=cost_usd,
                cost_basis=cost_basis,
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.FAILED,
                latency_ms=elapsed_ms,
                error_message=scrub_secrets(str(e)),
            )


class SubprocessTarget(Target):
    """Benchmarks an external process via stdin/stdout."""

    def __init__(
        self,
        target_id: str,
        name: str,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        pricing: Optional[TargetPricing] = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        super().__init__(
            target_id=target_id,
            name=name,
            target_type=TargetType.SUBPROCESS,
            capabilities=["subprocess", "cli"],
            pricing=pricing,
            timeout_seconds=timeout_seconds,
            max_retries=1,
            billing=BillingMode.LOCAL,
        )
        self.command = command
        self.env = env

    def execute(
        self,
        input_payload: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> TargetResult:
        start_time = time.perf_counter()
        input_bytes = json.dumps(input_payload).encode("utf-8")
        try:
            proc = subprocess.run(
                self.command,
                input=input_bytes,
                capture_output=True,
                timeout=self.timeout_seconds,
                env=self.env,
            )
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0

            if proc.returncode != 0:
                err = proc.stderr.decode("utf-8", errors="replace")
                return TargetResult(
                    target_id=self.target_id,
                    status=TargetStatus.FAILED,
                    latency_ms=elapsed_ms,
                    error_code=str(proc.returncode),
                    error_message=f"Process exited {proc.returncode}: {scrub_secrets(err)}",
                )

            stdout_text = proc.stdout.decode("utf-8", errors="replace").strip()
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.SUCCESS,
                output_text=stdout_text,
                latency_ms=elapsed_ms,
            )
        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.TIMEOUT,
                latency_ms=elapsed_ms,
                error_message=f"Command timed out after {self.timeout_seconds}s",
            )
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            return TargetResult(
                target_id=self.target_id,
                status=TargetStatus.FAILED,
                latency_ms=elapsed_ms,
                error_message=scrub_secrets(str(e)),
            )
