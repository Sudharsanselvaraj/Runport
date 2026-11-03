"""Generic classification benchmark runner.

Enforces runner guard order:
1. Authorization Check (LiveAuthorization if live)
2. Privacy Gate (data classification validation)
3. Preflight Budget & Context Check
4. Target / Transport Execution
5. Strict Validation
6. Persistence & Spend Booking
"""

import hashlib
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from runport.classification.contracts import ClassificationCase
from runport.classification.records import PredictionRecord, PredictionStore
from runport.classification.validators import validate_classification_output
from runport.core.budget import BudgetExceededError, BudgetService
from runport.core.live_guard import LiveAuthorization, require_live_authorization
from runport.providers.base import BaseProvider, LiveNotAuthorizedError, ProviderRequest
from runport.schemas.evaluation import DataClassification


@dataclass
class ClassificationRunSummary:
    run_id: str
    target_id: str
    n_cases: int
    n_ok: int = 0
    n_invalid: int = 0
    n_error: int = 0
    total_spend_usd: Decimal = Decimal("0")


class ClassificationRunner:
    """Orchestrates classification benchmarking under budget and privacy controls."""

    def __init__(
        self,
        provider: BaseProvider,
        budget_service: Optional[BudgetService] = None,
        store: Optional[PredictionStore] = None,
    ):
        self.provider = provider
        self.budget_service = budget_service or BudgetService()
        self.store = store

    def run_batch(
        self,
        cases: Sequence[ClassificationCase],
        target_id: str,
        run_id: Optional[str] = None,
        live_auth: Optional[LiveAuthorization] = None,
        allowed_labels: Optional[List[str]] = None,
        prompt_template: str = "{input}",
    ) -> ClassificationRunSummary:
        r_id = run_id or f"cls-run-{uuid.uuid4().hex[:8]}"
        summary = ClassificationRunSummary(run_id=r_id, target_id=target_id, n_cases=len(cases))

        # 1. Authorization check
        if live_auth is not None:
            require_live_authorization(live_auth, target_id)

        # 2. Privacy gate
        for c in cases:
            if c.data_classification == DataClassification.CONFIDENTIAL and not live_auth:
                raise LiveNotAuthorizedError(f"Case {c.case_id} is CONFIDENTIAL; live authorization required.")

        prompt_hash = f"sha256:{hashlib.sha256(prompt_template.encode()).hexdigest()[:16]}"
        dataset_hash = "synthetic-v1"

        for case in cases:
            # 3. Budget preflight
            status = self.budget_service.get_status()
            if status.remaining_total_usd <= Decimal("0.00"):
                raise BudgetExceededError("Budget limit exhausted before executing case.")

            prompt_text = prompt_template.format(input=case.input_text)
            req = ProviderRequest(
                model_id=target_id,
                messages=[{"role": "user", "content": prompt_text}],
                temperature=0.0,
                max_tokens=64,
                case_id=case.case_id,
            )

            # 4. Transport execution
            t0 = time.perf_counter()
            resp = self.provider.generate(req)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            # 5. Strict output validation
            val = validate_classification_output(resp.output_text, allowed_labels=allowed_labels)
            rec_status = "OK" if val.valid else "INVALID_OUTPUT"
            if not val.valid:
                summary.n_invalid += 1
            else:
                summary.n_ok += 1

            # 6. Record creation & spend booking
            spend_usd = resp.cost_usd if resp.cost_usd is not None else Decimal("0")
            summary.total_spend_usd += spend_usd

            rec = PredictionRecord(
                record_id=f"{r_id}:{case.case_id}:{target_id}",
                run_id=r_id,
                case_id=case.case_id,
                task="classification",
                model_key=target_id,
                requested_model_id=target_id,
                prompt_version=prompt_hash,
                dataset_version=dataset_hash,
                status=rec_status,
                predicted_label=val.label,
                raw_output=resp.output_text,
                prompt_tokens=resp.prompt_tokens,
                completion_tokens=resp.completion_tokens,
                latency_ms=elapsed_ms,
                cost_usd=spend_usd,
                cost_basis="PROVIDER_REPORTED" if resp.cost_usd is not None else "UNAVAILABLE",
                created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )

            if self.store:
                self.store.append(rec)

        return summary
