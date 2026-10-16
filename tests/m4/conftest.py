from __future__ import annotations

from datetime import UTC, datetime

import pytest

from trust_receipt.agents.models import ClaimExtraction, TaskSpecCandidate
from trust_receipt.agents.validation import confirm_task_candidate
from trust_receipt.models import Finding, SourceDescriptor, VerificationResult

ADDRESS_TOKEN = "0x1111111111111111111111111111111111111111"
ADDRESS_TREASURY = "0x2222222222222222222222222222222222222222"
ADDRESS_RECIPIENT = "0x3333333333333333333333333333333333333333"
HASH_A = "0x" + "aa" * 32
NOW = datetime(2026, 10, 7, 1, 0, tzinfo=UTC)


@pytest.fixture
def ready_candidate() -> TaskSpecCandidate:
    return TaskSpecCandidate.model_validate(
        {
            "schema_version": "1.0",
            "candidate_id": "candidate-1",
            "chain_id": 11_155_111,
            "token_address": ADDRESS_TOKEN,
            "treasury_addresses": [ADDRESS_TREASURY],
            "recipient_addresses": [ADDRESS_RECIPIENT],
            "start_block": 100,
            "end_block": 200,
            "exclusion_rules": [
                {
                    "rule_id": "exclude-internal",
                    "rule_type": "EXCLUDE_TREASURY_INTERNAL",
                    "reason": "Exclude transfers between confirmed treasury accounts.",
                }
            ],
            "max_records": 200,
            "ambiguities": [],
            "missing_fields": [],
            "clarification_questions": [],
        }
    )


@pytest.fixture
def confirmed_task(ready_candidate):
    return confirm_task_candidate(ready_candidate, task_id="task-1", confirmed_at=NOW)


@pytest.fixture
def claim_extraction() -> ClaimExtraction:
    return ClaimExtraction.model_validate(
        {
            "schema_version": "1.0",
            "report_id": "report-1",
            "claims": [
                {"claim_id": "total", "claim_type": "CLAIMED_TOTAL", "value": "120000"},
                {"claim_id": "count", "claim_type": "CLAIMED_COUNT", "value": 1},
                {"claim_id": "set", "claim_type": "TRANSFER_SET", "value": []},
            ],
            "ambiguities": [],
            "clarification_questions": [],
            "source_summary": "The report explicitly claims a total, count, and transfer set.",
        }
    )


@pytest.fixture
def failed_result() -> VerificationResult:
    finding = Finding.model_validate(
        {
            "finding_id": "finding-1",
            "finding_type": "MISSING_TRANSFER",
            "severity": "error",
            "expected": {"event_key": [11_155_111, HASH_A, 0]},
            "actual": None,
            "violated_rule": "Every eligible reference transfer must be reported.",
            "evidence_refs": ["rpc-log-1"],
            "explanation": "One eligible transfer is missing.",
            "status": "confirmed",
        }
    )
    source = SourceDescriptor.model_validate(
        {
            "source": "rpc",
            "source_id": "rpc-1",
            "retrieved_at": NOW,
            "complete": True,
            "details": {"pages": 1},
        }
    )
    return VerificationResult.model_validate(
        {
            "run_id": "run-1",
            "task_id": "task-1",
            "submission_id": "submission-1",
            "verifier_version": "1.0.0",
            "reference_sources": [source],
            "reference_complete": True,
            "evidence_sufficient": True,
            "calculated_total_base_units": "110000",
            "calculated_count": 2,
            "findings": [finding],
            "outcome": "FAIL",
            "inconclusive_reason": None,
            "started_at": NOW,
            "finished_at": NOW,
        }
    )
