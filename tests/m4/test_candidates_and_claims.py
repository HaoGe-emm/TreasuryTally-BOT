from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from trust_receipt.agents import AIValidationError, ClaimExtraction, TaskSpecCandidate
from trust_receipt.agents.validation import confirm_task_candidate, validate_claim_extraction
from trust_receipt.hashing import verify_task_spec_hash


def test_ready_candidate_becomes_a_deterministically_hashed_task(ready_candidate) -> None:
    task = confirm_task_candidate(
        ready_candidate,
        task_id="task-confirmed",
        confirmed_at=datetime(2026, 10, 7, tzinfo=UTC),
    )

    assert task.task_id == "task-confirmed"
    assert verify_task_spec_hash(task)
    assert "spec_hash" not in type(ready_candidate).model_fields


def test_candidate_requires_exact_missing_fields_and_questions(ready_candidate) -> None:
    missing = ready_candidate.model_dump(mode="json")
    missing.update(
        {
            "token_address": None,
            "missing_fields": ["token_address"],
            "clarification_questions": ["Which token address should be verified?"],
        }
    )
    candidate = TaskSpecCandidate.model_validate(missing)
    assert not candidate.ready_for_confirmation
    with pytest.raises(AIValidationError, match="missing or ambiguous"):
        confirm_task_candidate(candidate, task_id="task-1", confirmed_at=datetime.now(UTC))

    missing["missing_fields"] = []
    with pytest.raises(ValidationError, match="exactly identify"):
        TaskSpecCandidate.model_validate(missing)


@pytest.mark.parametrize(
    ("claim_type", "value", "message"),
    [
        ("CLAIMED_TOTAL", 120000, "decimal integer string"),
        ("CLAIMED_COUNT", "1", "non-negative integer"),
        ("TRANSFER_SET", {"event": "x"}, "JSON array"),
    ],
)
def test_claim_values_cannot_cross_their_type_boundary(claim_type, value, message) -> None:
    with pytest.raises(ValidationError, match=message):
        ClaimExtraction.model_validate(
            {
                "schema_version": "1.0",
                "report_id": "report-1",
                "claims": [{"claim_id": "claim-1", "claim_type": claim_type, "value": value}],
                "ambiguities": [],
                "clarification_questions": [],
                "source_summary": "Explicit report claim.",
            }
        )


def test_ambiguous_claims_cannot_enter_plan_generation() -> None:
    extraction = ClaimExtraction.model_validate(
        {
            "schema_version": "1.0",
            "report_id": "report-1",
            "claims": [],
            "ambiguities": [
                {
                    "target": "claimed_total",
                    "description": "The report contains two totals.",
                    "options": ["100", "200"],
                }
            ],
            "clarification_questions": ["Which total is the service claiming?"],
            "source_summary": "Two incompatible totals are present.",
        }
    )
    with pytest.raises(AIValidationError, match="clarified"):
        validate_claim_extraction(extraction)


def test_unknown_claim_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ClaimExtraction.model_validate(
            {
                "schema_version": "1.0",
                "report_id": "report-1",
                "claims": [{"claim_id": "x", "claim_type": "RUN_SHELL", "value": "whoami"}],
                "ambiguities": [],
                "clarification_questions": [],
                "source_summary": "Untrusted content.",
            }
        )


def test_conflicting_claims_of_the_same_type_require_clarification() -> None:
    with pytest.raises(ValidationError, match="claim types must be unique"):
        ClaimExtraction.model_validate(
            {
                "schema_version": "1.0",
                "report_id": "report-1",
                "claims": [
                    {"claim_id": "total-1", "claim_type": "CLAIMED_TOTAL", "value": "100"},
                    {"claim_id": "total-2", "claim_type": "CLAIMED_TOTAL", "value": "200"},
                ],
                "ambiguities": [],
                "clarification_questions": [],
                "source_summary": "Conflicting totals.",
            }
        )
