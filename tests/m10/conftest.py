from __future__ import annotations

from copy import deepcopy

import pytest

from tests.contracts.samples import receipt_data
from trust_receipt.hashing import receipt_hash, task_spec_hash
from trust_receipt.models.receipts import Receipt


@pytest.fixture
def make_receipt():
    def factory(
        *,
        receipt_id: str,
        task_id: str,
        service_id: str,
        outcome: str,
        created_at: str,
    ) -> Receipt:
        raw = deepcopy(receipt_data())
        raw["receipt_id"] = receipt_id
        raw["task_spec"]["task_id"] = task_id
        raw["task_spec"]["spec_hash"] = "0x" + "00" * 32
        raw["service_identity"]["service_id"] = service_id
        raw["service_identity"]["name"] = f"Service {service_id.upper()}"
        raw["verification_plan"]["task_id"] = task_id
        result = raw["verification_result"]
        result["task_id"] = task_id
        result["submission_id"] = f"submission-{receipt_id}"
        result["run_id"] = f"run-{receipt_id}"
        result["outcome"] = outcome
        raw["created_at"] = created_at
        result["started_at"] = created_at
        result["finished_at"] = created_at
        if outcome == "FAIL":
            result["findings"] = [
                {
                    "finding_id": f"finding-{receipt_id}",
                    "finding_type": "MISSING_TRANSFER",
                    "severity": "error",
                    "expected": {"count": 1},
                    "actual": {"count": 0},
                    "violated_rule": "COMPARE_EVENT_SET",
                    "evidence_refs": ["rpc-log-1"],
                    "explanation": "A confirmed transfer is missing.",
                    "status": "confirmed",
                }
            ]
        elif outcome == "INCONCLUSIVE":
            result["reference_complete"] = False
            result["reference_sources"][0]["complete"] = False
            result["evidence_sufficient"] = False
            result["calculated_total_base_units"] = None
            result["calculated_count"] = None
            result["inconclusive_reason"] = "Reference evidence is incomplete."
        task = Receipt.model_validate(raw).task_spec
        raw["task_spec"]["spec_hash"] = task_spec_hash(task)
        raw["receipt_hash"] = "0x" + "00" * 32
        draft = Receipt.model_validate(raw)
        return draft.model_copy(update={"receipt_hash": receipt_hash(draft)})

    return factory
